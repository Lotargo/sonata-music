import os
import torch
import torchaudio
import logging
from audiosr.pipeline import build_model, super_resolution
from pydub import AudioSegment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UpscalerService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        logger.info(f"UpscalerService initialized on {self.device}")

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

        try:
            # Perform super resolution
            waveform = super_resolution(
                self.model,
                input_path,
                seed=42,
                ddim_steps=ddim_steps,
                guidance_scale=guidance_scale
            )

            if waveform.dim() == 3:
                waveform = waveform.squeeze(0)

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Temporary wav file if we need to convert
            temp_wav = output_path if target_format.lower() == "wav" else output_path + ".tmp.wav"

            # Resample if needed
            if target_sample_rate != 48000:
                resampler = torchaudio.transforms.Resample(orig_freq=48000, new_freq=target_sample_rate)
                waveform = resampler(waveform)

            # Save as WAV first
            torchaudio.save(temp_wav, waveform.cpu(), target_sample_rate)

            if target_format.lower() != "wav":
                # Convert to target format using pydub
                audio = AudioSegment.from_wav(temp_wav)

                format_map = {
                    'mp3': 'mp3',
                    'flac': 'flac',
                    'ogg': 'ogg',
                    'vorbis': 'ogg'
                }
                out_fmt = format_map.get(target_format.lower(), target_format.lower())

                audio.export(output_path, format=out_fmt, bitrate=target_bitrate)

                # Clean up temp file
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)

            logger.info(f"Successfully saved upscaled audio to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error during upscaling: {e}")
            raise e

# Create a singleton instance
upscaler = UpscalerService()
