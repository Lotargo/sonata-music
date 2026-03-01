import os
import torch
import audiosr
import soundfile as sf
from .logger import logger
from .config import PROCESSED_FOLDER

class AudioUpscaler:
    def __init__(self, model_name="basic"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing AudioSR model '{model_name}' on {self.device}...")
        try:
            self.model = audiosr.build_model(model_name=model_name, device=self.device)
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def upscale(self, input_path, ddim_steps=50, guidance_scale=3.5):
        """
        Upscale the audio file at input_path and save it to the processed folder.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        filename = os.path.basename(input_path)
        name_without_ext = os.path.splitext(filename)[0]
        output_filename = f"{name_without_ext}_upscaled.wav"
        output_path = os.path.join(PROCESSED_FOLDER, output_filename)

        logger.info(f"Upscaling {input_path} (Steps: {ddim_steps}, Guidance: {guidance_scale})...")

        try:
            # super_resolution returns a numpy array of shape (1, T) or (T,)
            waveform = audiosr.super_resolution(
                self.model,
                input_path,
                seed=42,
                ddim_steps=ddim_steps,
                guidance_scale=guidance_scale
            )

            # Save using soundfile to ensure 48kHz and correct format
            # waveform is typically (1, channels, samples) or similar from torch models,
            # but AudioSR returns (1, T) for mono.
            if len(waveform.shape) == 3:
                waveform = waveform[0] # remove batch dim

            # Soundfile expects (samples, channels)
            if waveform.shape[0] < 10: # Likely (channels, samples)
                waveform = waveform.T

            sf.write(output_path, waveform, 48000)
            logger.info(f"Upscaling complete. Saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error during upscaling: {e}")
            raise
