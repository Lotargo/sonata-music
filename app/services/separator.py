import os
import torch
import gc
import logging
from demucs.apply import apply_model
from demucs.pretrained import get_model
from demucs.audio import save_audio
import soundfile as sf

logger = logging.getLogger(__name__)

class SeparatorService:
    def __init__(self):
        self.model_name = "htdemucs" # Fast, high quality hybrid transformer
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def separate_track(self, input_path, output_dir):
        """
        Separates a track into 4 stems: vocals, drums, bass, other.
        Returns a dictionary of paths to the generated stems.
        """
        logger.info(f"Starting separation for {input_path} on {self.device}")

        try:
            # 1. Load Model
            # We load it here and unload immediately to save VRAM for other steps
            model = get_model(self.model_name)
            model.to(self.device)

            # 2. Read Audio
            # Demucs expects (channels, samples) tensor
            wav, sr = sf.read(input_path)
            wav = wav.astype('float32') # Ensure float32 for PyTorch

            # Handle Mono -> Stereo
            if wav.ndim == 1:
                wav = wav.reshape(1, -1)
                wav = torch.tensor(wav) # (1, samples)
                wav = wav.repeat(2, 1) # (2, samples)
            else:
                wav = torch.tensor(wav).t() # (samples, channels) -> (channels, samples)

            # Normalize to match Demucs training (optional but good practice)
            ref = wav.mean(0)
            wav = (wav - ref.mean()) / (ref.std() + 1e-8)

            # Add batch dim: (1, 2, samples)
            wav = wav.unsqueeze(0).to(self.device)

            # 3. Inference
            # shifts=1 for speed (use 2+ for quality, but user wants speed/efficiency)
            sources = apply_model(model, wav, shifts=1, split=True, overlap=0.25, progress=False)[0]

            # sources shape: (4, 2, samples) -> [drums, bass, other, vocals] order usually
            # But demucs.apply returns sources in the order of model.sources
            source_names = model.sources # ['drums', 'bass', 'other', 'vocals']

            stem_paths = {}
            os.makedirs(output_dir, exist_ok=True)

            # 4. Save Stems
            for i, name in enumerate(source_names):
                source = sources[i].cpu() # (2, samples)
                filename = f"{name}.wav"
                path = os.path.join(output_dir, filename)

                # Save using soundfile (safe for our env)
                # source is (channels, samples), soundfile needs (samples, channels)
                sf.write(path, source.t().numpy(), model.samplerate, subtype='PCM_24')
                stem_paths[name] = path

            # 5. Cleanup
            del model
            del wav
            del sources
            if self.device == "cuda":
                torch.cuda.empty_cache()
            gc.collect()

            return stem_paths

        except Exception as e:
            logger.error(f"Separation failed: {e}")
            # Ensure cleanup happens even on error
            if 'model' in locals():
                del model
            if self.device == "cuda":
                torch.cuda.empty_cache()
            gc.collect()
            raise e

separator = SeparatorService()
