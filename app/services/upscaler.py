import os
import torch
import torchaudio
import logging
import subprocess
import traceback
import tempfile
import gc
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
    # Strictly use soundfile to avoid libtorchcodec issues
    try:
        data, sr = sf.read(filename)
        # soundfile returns (samples, channels) or (samples,)
        if data.ndim == 1:
            data = data[None, :]
        else:
            data = data.T  # Convert to (channels, samples)
        waveform = torch.from_numpy(data).float()
    except Exception as e:
        logger.error(f"sf.read failed in safe_read_wav_file: {e}")
        raise e

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

    def unload_model(self):
        """Unloads the model and frees VRAM/RAM."""
        if self.model is not None:
            logger.info("Unloading AudioSR model to free resources...")
            del self.model
            self.model = None

        # Force garbage collection
        gc.collect()

        # Clear CUDA cache if applicable
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def _process_channel_waveform(self, waveform, sr, ddim_steps, guidance_scale, seed):
        """
        Processes a single-channel waveform.
        Expects waveform shape: [1, samples]
        Returns upscaled waveform: [1, samples]
        """
        # Normalize waveform
        max_val = torch.max(torch.abs(waveform))
        if max_val > 0:
            waveform = waveform / max_val
        else:
            logger.warning("Audio appears to be silent (max value 0).")

        # Split into 5.12s segments
        segment_length = 5.12
        samples_per_segment = int(segment_length * sr)
        total_samples = waveform.shape[-1]
        num_segments = int(np.ceil(total_samples / samples_per_segment))

        processed_segments = []
        temp_segments = []

        logger.info(f"Processing {num_segments} segments sequentially for channel...")

        try:
            for i in range(num_segments):
                start_sample = i * samples_per_segment
                end_sample = min((i + 1) * samples_per_segment, total_samples)

                segment = waveform[:, start_sample:end_sample]
                original_length = segment.shape[-1]

                # Save segment to temporary file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_seg:
                    temp_seg_path = tmp_seg.name

                temp_segments.append(temp_seg_path)

                # segment is [1, samples] (mono)
                # sf.write expects [samples, channels] or [samples]
                sf.write(temp_seg_path, segment.T.numpy(), sr)

                # Call super_resolution
                out_seg = super_resolution(
                    self.model,
                    temp_seg_path,
                    seed=seed,
                    ddim_steps=ddim_steps,
                    guidance_scale=guidance_scale
                )
                
                if isinstance(out_seg, np.ndarray):
                    out_seg = torch.from_numpy(out_seg).float()
                else:
                    out_seg = out_seg.detach().cpu().float()
                
                # Trim if necessary.
                if out_seg.shape[-1] > original_length:
                    out_seg = out_seg[..., :original_length]
                
                processed_segments.append(out_seg)

                # Clean up temp file
                if os.path.exists(temp_seg_path):
                    os.remove(temp_seg_path)

            # Concatenate
            if len(processed_segments) > 0:
                full_waveform = torch.cat(processed_segments, dim=-1)
            else:
                 raise Exception("No segments processed")

            # Ensure we have [1, samples]
            if full_waveform.dim() == 3:
                 # Usually comes as [1, 1, samples] or [batch, channels, samples]
                full_waveform = full_waveform.squeeze(0)

            return full_waveform

        finally:
             for f in temp_segments:
                 if os.path.exists(f):
                     try:
                         os.remove(f)
                     except:
                         pass

    def process_track(self, input_path, output_path, ddim_steps=50, guidance_scale=3.5, seed=42,
                      target_format="wav", target_sample_rate=48000, target_bitrate="320k", batch_size=4):
        """
        Upscale the audio file at input_path and save to output_path.
        Supports FP16, custom steps, guidance, seed.
        """
        try:
            self.load_model()

            logger.info(f"Starting upscaling: {input_path} -> {output_path} "
                        f"(format: {target_format}, sr: {target_sample_rate}, "
                        f"br: {target_bitrate}, steps: {ddim_steps}, "
                        f"guidance: {guidance_scale}, seed: {seed})")

            temp_wav = None

            # Read file using soundfile
            try:
                data, sr = sf.read(input_path)
                if data.ndim == 1:
                    data = data[None, :]
                else:
                    data = data.T # Convert to [channels, samples]
                waveform = torch.from_numpy(data).float()
            except Exception as e:
                logger.error(f"Failed to read input file with sf.read: {e}")
                raise e

            logger.info(f"Loaded waveform shape: {waveform.shape}, sr: {sr}")

            # Resample to 48k
            if sr != 48000:
                logger.info("Resampling to 48000Hz...")
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=48000)
                waveform = resampler(waveform)
                sr = 48000

            # Check for Stereo
            channels = waveform.shape[0]
            logger.info(f"Processing audio with {channels} channel(s)")

            upscaled_waveform = None

            if channels == 1:
                # Process Mono
                upscaled_waveform = self._process_channel_waveform(waveform, sr, ddim_steps, guidance_scale, seed)
            elif channels == 2:
                # Process Stereo - Split channels
                logger.info("Stereo detected. Processing Left Channel...")
                left_channel = waveform[0:1, :]
                out_left = self._process_channel_waveform(left_channel, sr, ddim_steps, guidance_scale, seed)

                logger.info("Stereo detected. Processing Right Channel...")
                right_channel = waveform[1:2, :]
                out_right = self._process_channel_waveform(right_channel, sr, ddim_steps, guidance_scale, seed)

                # Combine
                # Ensure they are same length (should be, but just in case)
                min_len = min(out_left.shape[-1], out_right.shape[-1])
                out_left = out_left[..., :min_len]
                out_right = out_right[..., :min_len]

                upscaled_waveform = torch.cat([out_left, out_right], dim=0)
            else:
                 # For > 2 channels, just mix to mono for now or handle similarly.
                 # Let's fallback to mixing to mono then upscaling to avoid complexity if user uploads 5.1
                 logger.warning(f"Unsupported channel count {channels}. Downmixing to mono.")
                 waveform = torch.mean(waveform, dim=0, keepdim=True)
                 upscaled_waveform = self._process_channel_waveform(waveform, sr, ddim_steps, guidance_scale, seed)

            logger.info(f"Generated waveform shape: {upscaled_waveform.shape}, dtype: {upscaled_waveform.dtype}, device: {upscaled_waveform.device}")

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
                upscaled_waveform = resampler(upscaled_waveform)
                logger.info(f"Resampled waveform shape: {upscaled_waveform.shape}")

            # Calculate estimated size in MB
            est_size = (upscaled_waveform.shape[0] * upscaled_waveform.shape[1] * 4) / (1024 * 1024)
            logger.info(f"Estimated uncompressed size: {est_size:.2f} MB")

            # Save as WAV first
            if target_format.lower() in ["wav", "flac"]:
                logger.info("Attempting to save as 24-bit WAV")
                try:
                    # waveform is [channels, samples]
                    sf.write(temp_wav, upscaled_waveform.T.numpy(), target_sample_rate, subtype='PCM_24')
                except Exception as e:
                    logger.error(f"Failed to save 24-bit with sf: {e}")
                    # Fallback to 16-bit (PCM_16) if 24-bit fails
                    try:
                        logger.warning("Falling back to 16-bit WAV...")
                        sf.write(temp_wav, upscaled_waveform.T.numpy(), target_sample_rate, subtype='PCM_16')
                    except Exception as e2:
                        logger.error(f"Failed to save 16-bit with sf: {e2}")
                        raise e2
            else:
                try:
                    sf.write(temp_wav, upscaled_waveform.T.numpy(), target_sample_rate)
                except Exception as e:
                    logger.error(f"Failed to save temporary WAV with sf: {e}")
                    raise e

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
            raise e
        finally:
            self.unload_model()

# Create a singleton instance
upscaler = UpscalerService()
