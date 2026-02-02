import sys
import os
import numpy as np
from unittest.mock import MagicMock, patch

# --- MOCKS MUST BE BEFORE IMPORTS ---

# Mock Torch
mock_torch = MagicMock()
class MockTensor:
    def __init__(self, data): self.data = data
    def float(self): return self
    def numpy(self): return self.data
    def to(self, device): return self
    def __len__(self): return len(self.data)
    @property
    def shape(self): return self.data.shape
    def dim(self): return self.data.ndim
    def squeeze(self, *args): return self
    def unsqueeze(self, *args): return self
    # Support indexing
    def __getitem__(self, key):
        # Return new MockTensor if slice results in array
        res = self.data[key]
        if isinstance(res, np.ndarray):
             return MockTensor(res)
        return res

mock_torch.from_numpy.side_effect = lambda x: MockTensor(x)
mock_torch.cuda.is_available.return_value = False
sys.modules["torch"] = mock_torch

# Mock Torchaudio
sys.modules["torchaudio"] = MagicMock()

# Mock Pydub
sys.modules["pydub"] = MagicMock()

# Mock other deps
sys.modules["audiosr"] = MagicMock()
sys.modules["audiosr.pipeline"] = MagicMock()
sys.modules["audiosr.utils"] = MagicMock()
sys.modules["voicefixer"] = MagicMock()
sys.modules["noisereduce"] = MagicMock()
sys.modules["resampy"] = MagicMock()
sys.modules["demucs"] = MagicMock()
sys.modules["demucs.apply"] = MagicMock()
sys.modules["demucs.pretrained"] = MagicMock()
sys.modules["demucs.audio"] = MagicMock()

# Mock pedalboard
mock_pb = MagicMock()
class MockBoard:
    def __init__(self, *args, **kwargs): pass
    def append(self, *args, **kwargs): pass
    def __call__(self, audio, sr): return audio # Identity processing

mock_pb.Pedalboard = MockBoard
for cls in ["Compressor", "Limiter", "HighpassFilter", "HighShelfFilter",
            "LowShelfFilter", "PeakFilter", "Gain", "NoiseGate", "Distortion", "Reverb"]:
    setattr(mock_pb, cls, MagicMock())

sys.modules["pedalboard"] = mock_pb

# Setup VoiceFixer mock behavior
mock_vf = MagicMock()
sys.modules["voicefixer"].VoiceFixer = MagicMock(return_value=mock_vf)
def mock_restore(input, output, **kwargs):
    import shutil
    shutil.copy(input, output)
mock_vf.restore.side_effect = mock_restore

# --- IMPORTS ---
import soundfile as sf
import app.services.upscaler as upscaler_module
from app.services.upscaler import upscaler

def test_restoration_pipeline():
    print("Testing Restoration Pipeline...")

    # Mock Separator
    with patch("app.services.separator.separator.separate_track") as mock_separate:
        def side_effect_separate(input_path, output_dir):
            stems = ["vocals", "drums", "bass", "other"]
            paths = {}
            data, sr = sf.read(input_path)
            # Make sure data is 2D
            if data.ndim == 1: data = data[:, None]

            for stem in stems:
                path = os.path.join(output_dir, f"{stem}.wav")
                sf.write(path, data, sr)
                paths[stem] = path
            return paths

        mock_separate.side_effect = side_effect_separate

        # Mock noisereduce
        with patch("app.services.upscaler.nr.reduce_noise") as mock_nr:
            mock_nr.side_effect = lambda y, **kwargs: y # Identity function

            # Create input file
            input_path = "test_restoration_in.wav"
            output_path = "test_restoration_out.wav"
            sr = 44100
            # 1 second of noise
            data = np.random.uniform(-0.5, 0.5, (sr, 2)) # Stereo
            sf.write(input_path, data, sr)

            try:
                upscaler.process_track(
                    input_path,
                    output_path,
                    mode="restoration",
                    target_sample_rate=44100
                )

                # Check file exists
                assert os.path.exists(output_path)

                # Check output properties
                out_data, out_sr = sf.read(output_path)
                assert out_sr == 44100
                # Length should match (roughly)
                assert abs(len(out_data) - len(data)) < 100

                print("Restoration pipeline flow verified.")

            finally:
                if os.path.exists(input_path): os.remove(input_path)
                if os.path.exists(output_path): os.remove(output_path)
                if os.path.exists(output_path + ".tmp.wav"): os.remove(output_path + ".tmp.wav")

if __name__ == "__main__":
    test_restoration_pipeline()
