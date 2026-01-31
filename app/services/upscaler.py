import os
import torch
import torchaudio
import logging
from audiosr.pipeline import build_model, super_resolution

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

    def process_track(self, input_path, output_path, ddim_steps=50, guidance_scale=3.5):
        """
        Upscale the audio file at input_path and save to output_path.
        """
        self.load_model()

        logger.info(f"Starting upscaling: {input_path} -> {output_path}")

        try:
            # Perform super resolution
            # The function signature handles reading the file
            waveform = super_resolution(
                self.model,
                input_path,
                seed=42,
                ddim_steps=ddim_steps,
                guidance_scale=guidance_scale
            )

            # waveform shape expected: [1, channels, samples] or [channels, samples]
            # audiosr usually outputs 48kHz

            if waveform.dim() == 3:
                waveform = waveform.squeeze(0)

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Save the file
            torchaudio.save(output_path, waveform.cpu(), 48000)
            logger.info(f"Successfully saved upscaled audio to {output_path}")

            return True

        except Exception as e:
            logger.error(f"Error during upscaling: {e}")
            raise e

# Create a singleton instance
upscaler = UpscalerService()
