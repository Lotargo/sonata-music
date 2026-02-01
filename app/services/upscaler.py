import os
import torch
import torchaudio
import logging
import subprocess
import traceback
import tempfile
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
        Supports FP16, custom steps, guidance, seed.
        Batching logic has been removed in favor of robust sequential processing.
        """
        self.load_model()

        logger.info(f"Starting upscaling: {input_path} -> {output_path} "
                    f"(format: {target_format}, sr: {target_sample_rate}, "
                    f"br: {target_bitrate}, steps: {ddim_steps}, "
                    f"guidance: {guidance_scale}, seed: {seed})")

        temp_wav = None
        temp_segments = []
        try:
            # Read file (using our safe reader logic or similar)
            try:
                waveform, sr = torchaudio.load(input_path, backend="soundfile")
            except:
                data, sr = sf.read(input_path)
                if data.ndim == 1: data = data[None, :]
                else: data = data.T
                waveform = torch.from_numpy(data).float()
            
            logger.info(f"Loaded waveform shape: {waveform.shape}, sr: {sr}")

            # Resample to 48k
            if sr != 48000:
                logger.info("Resampling to 48000Hz...")
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=48000)
                waveform = resampler(waveform)
                sr = 48000
            
            # Mix to mono
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # Normalize waveform
            max_val = torch.max(torch.abs(waveform))
            if max_val > 0:
                waveform = waveform / max_val
            else:
                logger.warning("Audio appears to be silent (max value 0).")
            
            logger.info(f"Processed waveform shape: {waveform.shape}")

            # Split into 5.12s segments
            segment_length = 5.12
            samples_per_segment = int(segment_length * sr)
            total_samples = waveform.shape[-1]
            num_segments = int(np.ceil(total_samples / samples_per_segment))

            processed_segments = []
            
            logger.info(f"Processing {num_segments} segments sequentially...")

            for i in range(num_segments):
                start_sample = i * samples_per_segment
                end_sample = min((i + 1) * samples_per_segment, total_samples)

                segment = waveform[:, start_sample:end_sample]
                original_length = segment.shape[-1]

                # Save segment to temporary file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_seg:
                    temp_seg_path = tmp_seg.name

                temp_segments.append(temp_seg_path)
                try:
                    # Use soundfile directly to avoid torchaudio backend issues
                    # segment is [channels, samples], sf.write expects [samples, channels]
                    sf.write(temp_seg_path, segment.T.numpy(), sr)
                except Exception as e:
                    logger.warning(f"sf.write failed: {e}. Trying torchaudio.save fallback.")
                    try:
                         torchaudio.save(temp_seg_path, segment, sr, backend="soundfile")
                    except:
                         torchaudio.save(temp_seg_path, segment, sr)

                logger.info(f"Processing segment {i+1}/{num_segments} ({original_length} samples)")

                # Call super_resolution
                if self.device == "cuda":
                     with torch.autocast(device_type="cuda", dtype=torch.float16):
                         out_seg = super_resolution(
                            self.model,
                            temp_seg_path,
                            seed=seed,
                            ddim_steps=ddim_steps,
                            guidance_scale=guidance_scale
                        )
                else:
                    out_seg = super_resolution(
                        self.model,
                        temp_seg_path,
                        seed=seed,
                        ddim_steps=ddim_steps,
                        guidance_scale=guidance_scale
                    )
                
                # out_seg is likely on CPU or GPU? Detach and move to CPU immediately
                out_seg = out_seg.detach().cpu().float()
                
                # Trim if necessary.
                if out_seg.shape[-1] > original_length:
                    out_seg = out_seg[..., :original_length]
                elif out_seg.shape[-1] < original_length:
                     logger.warning(f"Output segment shorter than input: {out_seg.shape} vs {segment.shape}")
                
                processed_segments.append(out_seg)
                
                # Clean up temp file
                if os.path.exists(temp_seg_path):
                    os.remove(temp_seg_path)

            # Concatenate
            if len(processed_segments) > 0:
                waveform = torch.cat(processed_segments, dim=-1)
            else:
                 logger.error("No segments processed!")
                 raise Exception("No segments processed")

            # Ensure we have [channels, samples]
            if waveform.dim() == 3:
                waveform = waveform.squeeze(0)

            logger.info(f"Generated waveform shape: {waveform.shape}, dtype: {waveform.dtype}, device: {waveform.device}")

            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

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

            # Calculate estimated size in MB
            est_size = (waveform.shape[0] * waveform.shape[1] * 4) / (1024 * 1024)
            logger.info(f"Estimated uncompressed size: {est_size:.2f} MB")

            # Save as WAV first
            if target_format.lower() in ["wav", "flac"]:
                logger.info("Attempting to save as 24-bit WAV")
                try:
                    # waveform is [channels, samples]
                    sf.write(temp_wav, waveform.T.numpy(), target_sample_rate, subtype='PCM_24')
                except Exception as e:
                    logger.warning(f"Failed to save 24-bit with sf, falling back to torchaudio: {e}")
                    try:
                        torchaudio.save(temp_wav, waveform, target_sample_rate, bits_per_sample=24, backend="soundfile")
                    except:
                         torchaudio.save(temp_wav, waveform, target_sample_rate)
            else:
                try:
                    sf.write(temp_wav, waveform.T.numpy(), target_sample_rate)
                except:
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
            traceback.print_exc()
            if temp_wav and os.path.exists(temp_wav) and temp_wav != output_path:
                try:
                    os.remove(temp_wav)
                except:
                    pass
            for f in temp_segments:
                 if os.path.exists(f):
                     try:
                         os.remove(f)
                     except:
                         pass
            raise e

# Create a singleton instance
upscaler = UpscalerService()
