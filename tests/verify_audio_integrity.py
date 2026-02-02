import soundfile as sf
import numpy as np
import os
import tempfile
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.dsp import dsp

def verify_resampling():
    print("Verifying Resampling Integrity (44.1k -> 48k)...")

    temp_dir = tempfile.mkdtemp()

    # Create 10 second sine wave at 44100
    duration_sec = 5.0
    sr_orig = 44100
    t = np.linspace(0, duration_sec, int(sr_orig * duration_sec))
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio = np.stack([audio, audio], axis=1) # Stereo (Samples, Channels)

    # Save dummy stems
    names = ['vocals', 'drums', 'bass', 'other']
    stems_map = {}

    for name in names:
        path = os.path.join(temp_dir, f"{name}.wav")
        sf.write(path, audio, sr_orig)
        stems_map[name] = path

    # Process Stems requesting 48k output
    sr_target = 48000
    dummy_out = os.path.join(temp_dir, "output.wav")

    try:
        # returns (Channels, Samples)
        result_array = dsp.process_stems(stems_map, dummy_out, params=None, sample_rate=sr_target)

        # Check shape
        # Expected samples = 5.0 * 48000 = 240000
        expected_samples = int(duration_sec * sr_target)
        actual_samples = result_array.shape[1]

        print(f"Original Duration: {duration_sec}s")
        print(f"Target Rate: {sr_target}Hz")
        print(f"Expected Samples: {expected_samples}")
        print(f"Actual Samples:   {actual_samples}")

        # Tolerance check (resampling might add tiny padding)
        diff = abs(actual_samples - expected_samples)
        if diff < 100: # < 2ms error
            print("SUCCESS: Duration preserved correctly.")
        else:
            actual_duration = actual_samples / sr_target
            print(f"FAILURE: Duration drift detected! Output is {actual_duration:.4f}s")

    except Exception as e:
        print(f"FAILURE: Processing crashed: {e}")
    finally:
        import shutil
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    verify_resampling()
