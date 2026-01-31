import os
import torch
import torchaudio
import logging
import subprocess
from audiosr.pipeline import build_model, super_resolution
from pydub import AudioSegment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                logger.info("AudioSR model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load AudioSR model: {e}")
                raise e

    def process_track(self, input_path, output_path, ddim_steps=50, guidance_scale=3.5,
                      target_format="wav", target_sample_rate=48000, target_bitrate="320k"):
        """
        Upscale the audio file at input_path and save to output_path with desired format and quality.
        """
        self.load_model()

        logger.info(f"Starting upscaling: {input_path} -> {output_path} (format: {target_format}, sr: {target_sample_rate}, br: {target_bitrate})")

        temp_wav = None
        try:
            # Perform super resolution
            waveform = super_resolution(
                self.model,
                input_path,
                seed=42,
                ddim_steps=ddim_steps,
                guidance_scale=guidance_scale
            )

            # Ensure we have [channels, samples]
            if waveform.dim() == 3:
                waveform = waveform.squeeze(0)

            logger.info(f"Generated waveform shape: {waveform.shape}, dtype: {waveform.dtype}, device: {waveform.device}")

            # Safety check: if waveform is on GPU, move to CPU
            waveform = waveform.detach().cpu()

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
            # For lossless formats, we try to use 24-bit for professional quality
            if target_format.lower() in ["wav", "flac"]:
                logger.info("Attempting to save as 24-bit WAV")
                try:
                    # Explicitly use PCM_24 encoding if possible, or just bits_per_sample
                    # torchaudio.save on Windows might use different backends
                    torchaudio.save(temp_wav, waveform, target_sample_rate, bits_per_sample=24)
                except Exception as e:
                    logger.warning(f"Failed to save 24-bit, falling back to default: {e}")
                    torchaudio.save(temp_wav, waveform, target_sample_rate)
            else:
                torchaudio.save(temp_wav, waveform, target_sample_rate)

            if target_format.lower() != "wav":
                if not self.ffmpeg_available:
                    logger.error("FFmpeg not found! Cannot convert to lossy formats or FLAC.")
                    # We can't convert, so we might want to just keep it as WAV or fail
                    # For now, let's just keep it as WAV but rename it to the intended output
                    # but actually FLAC also needs ffmpeg in pydub.
                    # Let's try to rename temp_wav to output_path if we can't convert
                    if target_format.lower() == "flac":
                        # Some systems might have flac binary but not ffmpeg? Unlikely here.
                        pass

                logger.info(f"Converting to {target_format} using pydub")
                audio = AudioSegment.from_wav(temp_wav)

                format_map = {
                    'mp3': 'mp3',
                    'flac': 'flac',
                    'ogg': 'ogg',
                    'vorbis': 'ogg'
                }
                out_fmt = format_map.get(target_format.lower(), target_format.lower())

                # Only pass bitrate for lossy formats
                if out_fmt in ['mp3', 'ogg']:
                    audio.export(output_path, format=out_fmt, bitrate=target_bitrate)
                else:
                    audio.export(output_path, format=out_fmt)

                # Clean up temp file
                if temp_wav and os.path.exists(temp_wav) and temp_wav != output_path:
                    os.remove(temp_wav)

            logger.info(f"Successfully saved upscaled audio to {output_path}. Final file size: {os.path.getsize(output_path) / (1024*1024):.2f} MB")
            return True

        except Exception as e:
            logger.error(f"Error during upscaling: {e}")
            # Cleanup temp file on error
            if temp_wav and os.path.exists(temp_wav) and temp_wav != output_path:
                try:
                    os.remove(temp_wav)
                except:
                    pass
            raise e

# Create a singleton instance
upscaler = UpscalerService()
