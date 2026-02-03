
import numpy as np
import torch
from app.services.upscaler import safe_lowpass_filter

def verify_kwargs_signature():
    print("Verifying safe_lowpass_filter signature with kwargs...")

    fs = 48000
    cutoff = 20000

    # Case 1: Standard Positional
    try:
        print("Testing positional args...")
        wf = np.zeros((1, 1024))
        safe_lowpass_filter(wf, cutoff, fs)
        print("Success: Positional args.")
    except Exception as e:
        print(f"Failed positional: {e}")
        raise e

    # Case 2: Keyword 'x' (AudioSR style)
    try:
        print("Testing keyword arg 'x'...")
        wf = np.zeros((1, 1024))
        # Call with x=...
        safe_lowpass_filter(x=wf, cutoff_freq=cutoff, sample_rate=fs)
        print("Success: Keyword 'x'.")
    except Exception as e:
        print(f"Failed keyword 'x': {e}")
        raise e

    # Case 3: Keyword 'x' + mixed
    try:
        print("Testing mixed args with 'x'...")
        wf = np.zeros((1, 1024))
        safe_lowpass_filter(cutoff_freq=cutoff, sample_rate=fs, x=wf, order=6)
        print("Success: Mixed args.")
    except Exception as e:
        print(f"Failed mixed: {e}")
        raise e

if __name__ == "__main__":
    verify_kwargs_signature()
