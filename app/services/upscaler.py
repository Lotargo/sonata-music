import os
import torch
import torchaudio
import logging
import subprocess
from audiosr.pipeline import build_model, super_resolution
# Explicitly import where we need to patch
import audiosr.utils
import audiosr.pipeline
import soundfile as sf
import numpy as np
from pydub import AudioSegment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Monkey-patch audiosr.utils.read_wav_file to be more robust
def safe_read_wav_file(filename):
    try:
        # Try explicit backend first to avoid torchcodec issues
        waveform, sr = torchaudio.load(filename, backend="soundfile")
    except Exception as e:
        logger.warning(f"torchaudio.load with backend='soundfile' failed: {e}. Trying fallback to sf.read.")
        try:
            # Fallback to soundfile directly
            data, sr = sf.read(filename)
            # soundfile returns (samples, channels) or (samples,)
            if data.ndim == 1:
                data = data[None, :]
            else:
                data = data.T  # Convert to (channels, samples)
            waveform = torch.from_numpy(data).float()
        except Exception as e2:
            logger.error(f"Fallback to sf.read also failed: {e2}")
            # Try default torchaudio.load as last resort (might trigger the original error)
            waveform, sr = torchaudio.load(filename)

    duration = waveform.size(-1) / sr

    if(duration > 10.24):
        logger.warning(f"Audio is {duration:.2f}s, which is longer than 10.24s. It will be truncated/chunked.")

    if(duration % 5.12 != 0):
        pad_duration = duration + (5.12 - duration % 5.12)
    else:
        pad_duration = duration

    target_frame = int(pad_duration * 100)

    waveform = torchaudio.functional.resample(waveform, sr, 48000)

    # audiosr logic: take first channel (mono)
    # waveform shape is [channels, samples] -> .numpy()[0, ...] gets [samples,]
    waveform = waveform.numpy()[0, ...]

    waveform = audiosr.utils.normalize_wav(waveform)

    # pad_wav pads to target_length and returns numpy array
    waveform = waveform[None, ...]
    waveform = audiosr.utils.pad_wav(waveform, target_length=int(48000 * pad_duration))
    return waveform, target_frame, pad_duration

# Apply monkey patch to audiosr.utils
logger.info("Applying monkey-patch to audiosr.utils.read_wav_file")
audiosr.utils.read_wav_file = safe_read_wav_file

class UpscalerService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.ffmpeg_available = self._check_ffmpeg()
        logger.info(f"UpscalerService initialized on {self.device}. FFmpeg available: {self.ffmpeg_available}")

    def _check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def load_model(self):
        if self.model is None:
            logger.info("Loading AudioSR model...")
            try:
                # "basic" is the default model.
                self.model = build_model(model_name="basic", device=self.device)

                # Apply FP16 quantization if on CUDA
                if self.device == "cuda":
                    logger.info("Converting model to FP16 for speedup on CUDA.")
                    self.model = self.model.half()

                logger.info("AudioSR model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load AudioSR model: {e}")
                raise e

    def process_track(self, input_path, output_path, ddim_steps=50, guidance_scale=3.5, seed=42,
                      target_format="wav", target_sample_rate=48000, target_bitrate="320k", batch_size=4):
        """
        Upscale the audio file at input_path and save to output_path.
        Supports FP16, custom steps, guidance, seed, and batch processing for segments.
        """
        self.load_model()

        logger.info(f"Starting upscaling: {input_path} -> {output_path} "
                    f"(format: {target_format}, sr: {target_sample_rate}, "
                    f"br: {target_bitrate}, steps: {ddim_steps}, "
                    f"guidance: {guidance_scale}, seed: {seed}, batch_size: {batch_size})")

        temp_wav = None
        try:
            # Check if input is long and needs segmentation/batching
            # Audiosr default pipeline truncates or processes single segment.
            # To support long files with batching, we need to manually chunk.

            # Read file (using our safe reader)
            # read_wav_file returns [1, samples] normalized and padded to 5.12s
            # But for long files, we want to read the raw full file first to chunk it ourselves.
            try:
                waveform, sr = torchaudio.load(input_path, backend="soundfile")
            except:
                data, sr = sf.read(input_path)
                if data.ndim == 1: data = data[None, :]
                else: data = data.T
                waveform = torch.from_numpy(data).float()

            # Resample to 48k
            if sr != 48000:
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=48000)
                waveform = resampler(waveform)
                sr = 48000

            # Mix to mono
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            # Duration
            duration = waveform.shape[-1] / sr
            segment_length = 5.12 # AudioSR standard
            samples_per_segment = int(segment_length * sr)

            if duration <= segment_length * 2: # Short file, use default pipeline
                 if self.device == "cuda":
                    with torch.autocast(device_type="cuda", dtype=torch.float16):
                         waveform = super_resolution(
                            self.model,
                            input_path,
                            seed=seed,
                            ddim_steps=ddim_steps,
                            guidance_scale=guidance_scale
                        )
                 else:
                    waveform = super_resolution(
                        self.model,
                        input_path,
                        seed=seed,
                        ddim_steps=ddim_steps,
                        guidance_scale=guidance_scale
                    )
            else:
                # Long file: Batch processing
                logger.info(f"Audio is {duration:.2f}s long. Processing in batches of size {batch_size}...")

                # Split into segments
                num_segments = int(np.ceil(waveform.shape[-1] / samples_per_segment))
                segments = []

                # Create segments with padding if needed
                pad_len = num_segments * samples_per_segment - waveform.shape[-1]
                if pad_len > 0:
                    waveform = torch.nn.functional.pad(waveform, (0, pad_len))

                # Slice segments
                for i in range(num_segments):
                    seg = waveform[:, i*samples_per_segment : (i+1)*samples_per_segment]
                    segments.append(seg)

                # Process batches
                processed_segments = []

                # Function to process a batch of tensors
                def process_batch_tensors(batch_tensors):
                    # Extract features for each item in batch
                    batch_log_mel = []
                    batch_stft = []
                    batch_waveform = []
                    batch_lowpass_mel = []

                    target_frame = 100 * 5.12 # 512

                    for wav in batch_tensors:
                        # wav is [1, samples]
                        # wav_feature_extraction expects 2D numpy array [1, samples]
                        # because it blindly slices index 0.
                        wav_np = wav.numpy() # [1, samples]

                        log_mel, stft = audiosr.utils.wav_feature_extraction(wav_np, int(target_frame))

                        # Prepare inference dict for lowpass
                        mini_batch = {
                            "waveform": wav,
                            "sampling_rate": 48000
                        }

                        lp_dict = audiosr.utils.lowpass_filtering_prepare_inference(mini_batch)
                        wav_lp = lp_dict["waveform_lowpass"]

                        # Extract lowpass features
                        # wav_lp might be [samples] (1D) because lowpass return 1D
                        # We must reshape to [1, samples] for wav_feature_extraction
                        wav_lp_np = wav_lp.numpy()
                        if wav_lp_np.ndim == 1:
                            wav_lp_np = wav_lp_np[None, :]

                        lp_mel, lp_stft = audiosr.utils.wav_feature_extraction(wav_lp_np, int(target_frame))

                        batch_log_mel.append(torch.FloatTensor(log_mel).unsqueeze(0))
                        batch_stft.append(torch.FloatTensor(stft).unsqueeze(0))
                        batch_waveform.append(wav.unsqueeze(0)) # [1, 1, samples]
                        batch_lowpass_mel.append(torch.FloatTensor(lp_mel).unsqueeze(0))

                    # Stack
                    final_batch = {
                        "log_mel_spec": torch.cat(batch_log_mel, dim=0), # [B, 1, F, T]
                        "lowpass_mel": torch.cat(batch_lowpass_mel, dim=0),
                        "waveform": torch.cat(batch_waveform, dim=0),
                    }

                    # Move to device
                    for k in final_batch:
                        final_batch[k] = final_batch[k].to(self.device)
                        if self.device == "cuda":
                            final_batch[k] = final_batch[k].half() # Cast if model is half

                    # Inference
                    with torch.no_grad():
                        out = self.model.generate_batch(
                            final_batch,
                            unconditional_guidance_scale=guidance_scale,
                            ddim_steps=ddim_steps,
                            duration=5.12
                        )

                    return out.cpu().float()

                # Loop through chunks
                for i in range(0, len(segments), batch_size):
                    batch_chunk = segments[i : i + batch_size]
                    logger.info(f"Processing batch {i//batch_size + 1}/{(len(segments)+batch_size-1)//batch_size}")

                    # Ensure autocast is active
                    if self.device == "cuda":
                        with torch.autocast(device_type="cuda", dtype=torch.float16):
                            out_batch = process_batch_tensors(batch_chunk)
                    else:
                        out_batch = process_batch_tensors(batch_chunk)

                    for j in range(out_batch.shape[0]):
                        processed_segments.append(out_batch[j])

                # Concatenate
                waveform = torch.cat(processed_segments, dim=-1)

                # Trim padding
                if pad_len > 0:
                    waveform = waveform[..., :-pad_len]

            # Ensure we have [channels, samples]
            if waveform.dim() == 3:
                waveform = waveform.squeeze(0)

            logger.info(f"Generated waveform shape: {waveform.shape}, dtype: {waveform.dtype}, device: {waveform.device}")

            # Safety check: if waveform is on GPU, move to CPU
            waveform = waveform.detach().cpu().float()

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Temporary wav file if we need to convert or if saving to WAV
            if target_format.lower() == "wav":
                temp_wav = output_path
            else:
                temp_wav = output_path + ".tmp.wav"

            # Resample if needed
            if target_sample_rate != 48000:
                logger.info(f"Resampling from 48000 to {target_sample_rate}")
                resampler = torchaudio.transforms.Resample(orig_freq=48000, new_freq=target_sample_rate)
                waveform = resampler(waveform)
                logger.info(f"Resampled waveform shape: {waveform.shape}")

            # Calculate estimated size in MB: samples * channels * bytes_per_sample / 1024 / 1024
            # Using 4 bytes for float32 (internal) or 3 bytes for 24-bit
            est_size = (waveform.shape[0] * waveform.shape[1] * 4) / (1024 * 1024)
            logger.info(f"Estimated uncompressed size: {est_size:.2f} MB")

            # Save as WAV first
            if target_format.lower() in ["wav", "flac"]:
                logger.info("Attempting to save as 24-bit WAV")
                try:
                    torchaudio.save(temp_wav, waveform, target_sample_rate, bits_per_sample=24)
                except Exception as e:
                    logger.warning(f"Failed to save 24-bit, falling back to default: {e}")
                    torchaudio.save(temp_wav, waveform, target_sample_rate)
            else:
                torchaudio.save(temp_wav, waveform, target_sample_rate)

            if target_format.lower() != "wav":
                if not self.ffmpeg_available:
                    logger.error("FFmpeg not found! Cannot convert to lossy formats or FLAC.")
                else:
                    logger.info(f"Converting to {target_format} using pydub")
                    audio = AudioSegment.from_wav(temp_wav)

                    format_map = {
                        'mp3': 'mp3',
                        'flac': 'flac',
                        'ogg': 'ogg',
                        'vorbis': 'ogg'
                    }
                    out_fmt = format_map.get(target_format.lower(), target_format.lower())

                    if out_fmt in ['mp3', 'ogg']:
                        audio.export(output_path, format=out_fmt, bitrate=target_bitrate)
                    else:
                        audio.export(output_path, format=out_fmt)

                    if temp_wav and os.path.exists(temp_wav) and temp_wav != output_path:
                        os.remove(temp_wav)

            logger.info(f"Successfully saved upscaled audio to {output_path}. Final file size: {os.path.getsize(output_path) / (1024*1024):.2f} MB")
            return True

        except Exception as e:
            logger.error(f"Error during upscaling: {e}")
            if temp_wav and os.path.exists(temp_wav) and temp_wav != output_path:
                try:
                    os.remove(temp_wav)
                except:
                    pass
            raise e

# Create a singleton instance
upscaler = UpscalerService()
