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
sys.modules["torchaudio"] = MagicMock()
sys.modules["pydub"] = MagicMock()

# Mock dependencies
sys.modules["audiosr"] = MagicMock()
sys.modules["audiosr.pipeline"] = MagicMock()
sys.modules["audiosr.utils"] = MagicMock()
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

# --- IMPORTS ---
import soundfile as sf
# We need to make sure dsp uses the mocked pedalboard
# Since we sys.modules["pedalboard"] is set, app.services.dsp will import it
import app.services.upscaler as upscaler_module
from app.services.upscaler import upscaler
from app.services.dsp import dsp

def test_suno_enhancer_pipeline():
    print("Testing Suno Enhancer Restoration Pipeline...")

    # Mock Separator
    # We patch the instance method on the separator object imported in upscaler
    with patch("app.services.separator.separator.separate_track") as mock_separate:
        def side_effect_separate(input_path, output_dir):
            print(f"Mock Separator called for {input_path}")
            stems = ["vocals", "drums", "bass", "other"]
            paths = {}
            data, sr = sf.read(input_path)
            # Make sure data is 2D
            if data.ndim == 1: data = data[:, None]

            # Divide by 4 so when we sum them we get original amplitude (roughly)
            stem_data = data * 0.25

            for stem in stems:
                path = os.path.join(output_dir, f"{stem}.wav")
                sf.write(path, stem_data, sr)
                paths[stem] = path
            return paths

        mock_separate.side_effect = side_effect_separate

        # Spy on dsp.apply_suno_restoration
        with patch.object(dsp, 'apply_suno_restoration', wraps=dsp.apply_suno_restoration) as mock_dsp_polish:

            # Create input file
            input_path = "test_suno_in.wav"
            output_path = "test_suno_out.wav"
            sr = 44100
            # 1 second of random noise (simulating audio)
            data = np.random.uniform(-0.5, 0.5, (sr, 2)) # Stereo
            sf.write(input_path, data, sr)

            try:
                print("Running process_track with mode='restoration'...")
                result = upscaler.process_track(
                    input_path,
                    output_path,
                    mode="restoration",
                    target_sample_rate=44100
                )

                assert result is True

                # Check file exists
                assert os.path.exists(output_path)

                # Check output properties
                out_data, out_sr = sf.read(output_path)
                assert out_sr == 44100

                # Check that separator was called
                mock_separate.assert_called_once()

                # Check that DSP polish was called
                mock_dsp_polish.assert_called_once()

                print("Suno Enhancer pipeline flow verified successfully!")

            except Exception as e:
                print(f"Test failed with exception: {e}")
                raise e
            finally:
                if os.path.exists(input_path): os.remove(input_path)
                if os.path.exists(output_path): os.remove(output_path)
                if os.path.exists(output_path + ".tmp.wav"): os.remove(output_path + ".tmp.wav")

if __name__ == "__main__":
    test_suno_enhancer_pipeline()
