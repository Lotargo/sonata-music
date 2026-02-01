import soundfile as sf
import numpy as np
import os
import tempfile
import resampy
from pedalboard import Pedalboard, Gain

def debug_process_stems_robust():
    print("Starting Robust Stem Processing Debug...")

    # Simulate params
    sample_rate = 48000

    # Create dummy stems
    stems_map = {}
    temp_dir = tempfile.mkdtemp()

    names = ['vocals', 'drums', 'bass', 'other']
    N = 10000 # samples

    # CASE 1: Normal (Samples, Channels)
    print("Case 1: Normal (Samples, Channels)")
    audio = np.random.uniform(-0.5, 0.5, (N, 2)).astype(np.float32)
    path = os.path.join(temp_dir, "vocals.wav")
    sf.write(path, audio, 44100)
    stems_map['vocals'] = path

    # CASE 2: Already Transposed (Channels, Samples) - unlikely for sf.read but good to test robust logic
    # sf.write expects (S, C) so we write it transposed to simulate reading it back wrong?
    # Actually we can't force sf.read to return (C, S) easily without mocking.
    # We will trust the logic handles (S, C) correctly first.

    loaded_stems = {}
    max_len = 0

    print("\n--- Loading & Resampling ---")
    for name, path in stems_map.items():
        data, sr = sf.read(path)
        print(f"[{name}] Read shape: {data.shape}, sr: {sr}")

        # --- NEW ROBUST LOGIC ---
        if data.ndim == 1:
            data = data[np.newaxis, :] # (1, Samples)
        else:
            # If dim0 > dim1 (Samples > Channels), transpose
            if data.shape[0] > data.shape[1]:
                print(f"[{name}] Transposing from {data.shape}")
                data = data.T # (Samples, Channels) -> (Channels, Samples)
            else:
                print(f"[{name}] Keeping shape {data.shape}")

        # Resample if needed
        if sr != sample_rate:
            data = resampy.resample(data, sr, sample_rate, axis=1)
        # ------------------------

        data = data.astype(np.float32)
        loaded_stems[name] = data
        if data.shape[1] > max_len:
            max_len = data.shape[1]

    print(f"\nMax Length: {max_len}")

    # Simulate mix
    print("\n--- Mixing ---")
    mix = np.zeros((2, max_len), dtype=np.float32)
    print(f"Mix initialized shape: {mix.shape}")

    for name, audio in loaded_stems.items():
        print(f"Adding {name} with shape {audio.shape}")

        # Pad if needed (missing from debug script but present in real code)
        if audio.shape[1] < max_len:
             pad = np.zeros((audio.shape[0], max_len - audio.shape[1]), dtype=np.float32)
             audio = np.concatenate([audio, pad], axis=1)

        # Ensure stereo
        if audio.shape[0] == 1:
            audio = np.concatenate([audio, audio], axis=0)

        try:
            mix += audio
            print(f"Added {name} successfully.")
        except Exception as e:
            print(f"FAILED adding {name}: {e}")
            raise e

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    debug_process_stems_robust()
