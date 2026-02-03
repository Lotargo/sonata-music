
import numpy as np
import scipy.signal
import torch
# We need to import the monkey-patched version, so we import upscaler service
from app.services.upscaler import safe_lowpass_filter

def verify_fix():
    print("Verifying AudioSR lowpass fix...")

    fs = 48000

    # Case 2: Invalid cutoff (Nyquist) - Should now pass
    cutoff = 24000
    print(f"Testing fix: cutoff={cutoff}, fs={fs}")
    try:
        # Dummy waveform: numpy array
        waveform = np.zeros((1, 1024))
        filtered = safe_lowpass_filter(waveform, cutoff, fs)
        print("Success: Function returned without crashing.")
    except Exception as e:
        print(f"Failed: {e}")
        raise e

    # Case 3: Invalid cutoff (Above Nyquist) - Should now pass
    cutoff = 25000
    print(f"Testing fix (High): cutoff={cutoff}, fs={fs}")
    try:
        # Dummy waveform: torch tensor
        waveform = torch.zeros((1, 1024))
        filtered = safe_lowpass_filter(waveform, cutoff, fs)
        print("Success: Function returned without crashing (Tensor support).")
    except Exception as e:
        print(f"Failed: {e}")
        raise e

if __name__ == "__main__":
    verify_fix()
