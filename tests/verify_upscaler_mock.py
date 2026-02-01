import sys
import os
import torch
import torchaudio
from unittest.mock import MagicMock

# Mock audiosr modules BEFORE importing app.services.upscaler
mock_audiosr = MagicMock()
sys.modules["audiosr"] = mock_audiosr
sys.modules["audiosr.pipeline"] = MagicMock()
sys.modules["audiosr.utils"] = MagicMock()

# Setup mocks for functions used in upscaler.py
# normalize_wav is used in safe_read_wav_file
def mock_normalize_wav(waveform):
    return waveform
sys.modules["audiosr.utils"].normalize_wav = mock_normalize_wav

# pad_wav is used in safe_read_wav_file
def mock_pad_wav(waveform, target_length):
    # Just pad with zeros if needed, or return as is for mock
    import numpy as np
    current_len = waveform.shape[-1]
    if current_len < target_length:
        return np.pad(waveform, ((0,0), (0, target_length - current_len)))
    return waveform
sys.modules["audiosr.utils"].pad_wav = mock_pad_wav

# Mock pipeline functions
mock_build_model = MagicMock()
mock_super_resolution = MagicMock()

sys.modules["audiosr.pipeline"].build_model = mock_build_model
sys.modules["audiosr.pipeline"].super_resolution = mock_super_resolution

# Now import the service
# It will see our mocks
from app.services.upscaler import upscaler

def test_upscaler_sequential_logic():
    print("Testing upscaler sequential logic...")

    # Setup mock model
    upscaler.model = MagicMock()

    # Setup mock super_resolution to return a dummy waveform
    # It receives a file path.
    # We simulate that super_resolution returns a 5.12s waveform (standard behavior of AudioSR)
    # 48000 * 5.12 = 245760 samples
    def side_effect_super_resolution(model, input_file, **kwargs):
        # Return random noise of 5.12s length
        return torch.randn(1, 245760)

    mock_super_resolution.side_effect = side_effect_super_resolution

    # Create a dummy input file (12 seconds)
    sr = 48000
    duration = 12.0
    total_samples = int(sr * duration)
    waveform = torch.randn(1, total_samples)
    input_path = "test_input.wav"
    output_path = "test_output.wav"

    # Save dummy input
    try:
        torchaudio.save(input_path, waveform, sr, backend="soundfile")
    except:
        # Fallback if specific backend kwarg fails (depends on torchaudio version)
        import soundfile as sf
        sf.write(input_path, waveform.squeeze().numpy(), sr)

    try:
        print(f"Processing {duration}s audio file...")
        upscaler.process_track(input_path, output_path)

        # Verify calls
        # 12s split into 5.12, 5.12, 1.76
        # Expected 3 calls to super_resolution
        print(f"super_resolution call count: {mock_super_resolution.call_count}")
        assert mock_super_resolution.call_count == 3, f"Expected 3 calls, got {mock_super_resolution.call_count}"

        # Verify output duration
        if not os.path.exists(output_path):
            raise FileNotFoundError("Output file was not created")

        import soundfile as sf
        data, out_sr = sf.read(output_path)
        # data is [samples, channels] or [samples]
        samples = data.shape[0]

        print(f"Output duration: {samples/out_sr:.2f}s")

        # Tolerance for float errors/rounding
        diff = abs(samples - waveform.shape[-1])
        print(f"Sample difference: {diff}")
        assert diff < 100, f"Length mismatch: {samples} vs {waveform.shape[-1]}"

        print("Test passed successfully!")

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == "__main__":
    test_upscaler_sequential_logic()
