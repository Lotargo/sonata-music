import soundfile as sf
import numpy as np
import os
import tempfile
import resampy
from pedalboard import Pedalboard, Gain

def debug_process_stems():
    print("Starting Stem Processing Debug...")

    # Simulate params
    sample_rate = 48000

    # Create dummy stems
    stems_map = {}
    temp_dir = tempfile.mkdtemp()

    names = ['vocals', 'drums', 'bass', 'other']
    N = 10000 # samples

    for name in names:
        # Create stereo audio (Samples, Channels) as sf.write expects
        # We simulate a slight mismatch in length to test padding
        length = N + np.random.randint(-100, 100)
        audio = np.random.uniform(-0.5, 0.5, (length, 2)).astype(np.float32)
        path = os.path.join(temp_dir, f"{name}.wav")
        sf.write(path, audio, 44100) # Source is 44.1k to trigger resampling path
        stems_map[name] = path

    print(f"Created dummy stems in {temp_dir}")

    # --- Simulate Logic from dsp.py ---

    loaded_stems = {}
    max_len = 0

    print("\n--- Loading & Resampling ---")
    for name, path in stems_map.items():
        data, sr = sf.read(path)
        print(f"[{name}] Read shape: {data.shape}, sr: {sr}")

        # Resample logic copy-paste
        if sr != sample_rate:
            # logic from dsp.py
            if data.ndim == 1:
                data = data[np.newaxis, :]
            else:
                data = data.T # Now (channels, samples)

            print(f"[{name}] Before resample: {data.shape}")
            data = resampy.resample(data, sr, sample_rate, axis=1)
            print(f"[{name}] After resample: {data.shape}")
        else:
            if data.ndim == 1:
                data = data[np.newaxis, :]
            else:
                data = data.T # (channels, samples)

        data = data.astype(np.float32)
        loaded_stems[name] = data
        if data.shape[1] > max_len:
            max_len = data.shape[1]

    print(f"\nMax Length: {max_len}")

    # Padding
    print("\n--- Padding ---")
    for name in loaded_stems:
        curr = loaded_stems[name]
        if curr.shape[1] < max_len:
            pad = np.zeros((curr.shape[0], max_len - curr.shape[1]), dtype=np.float32)
            loaded_stems[name] = np.concatenate([curr, pad], axis=1)
        print(f"[{name}] Padded shape: {loaded_stems[name].shape}")

    # Processing (Simulate Pedalboard)
    print("\n--- Processing Chains ---")
    board = Pedalboard([Gain(gain_db=0)])

    if 'vocals' in loaded_stems:
        # Pedalboard expects (channels, samples)
        # Returns (channels, samples)
        out = board(loaded_stems['vocals'], sample_rate)
        print(f"[vocals] Pedalboard Output: {out.shape}")
        loaded_stems['vocals'] = out

    # Simulate mix
    print("\n--- Mixing ---")
    mix = np.zeros((2, max_len), dtype=np.float32)
    print(f"Mix initialized shape: {mix.shape}")

    for name, audio in loaded_stems.items():
        print(f"Adding {name} with shape {audio.shape}")
        try:
            # Ensure stereo
            if audio.shape[0] == 1:
                audio = np.concatenate([audio, audio], axis=0)
            mix += audio
            print(f"Added {name} successfully.")
        except Exception as e:
            print(f"FAILED adding {name}: {e}")

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    debug_process_stems()
