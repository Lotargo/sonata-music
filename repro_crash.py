
import numpy as np
import scipy.signal
import torch
import audiosr.lowpass

def reproduction():
    print("Reproducing AudioSR lowpass crash...")

    # Simulate the call stack
    # lowpass(input, dim=..., lowpass_cutoff=...)
    # -> lowpass_filter(input, cutoff=..., fs=...)
    # -> scipy.signal.ellip(..., Wn=cutoff/(fs/2))

    fs = 48000
    # AudioSR typically simulates a lower quality input.
    # If it tries to filter at a frequency >= fs/2, it crashes.

    # Case 1: Valid cutoff
    cutoff = 12000
    Wn = cutoff / (fs / 2)
    print(f"Valid case: cutoff={cutoff}, fs={fs}, Wn={Wn}")
    try:
        scipy.signal.ellip(6, 0.1, 60, Wn, btype="low", output="sos")
        print("Success.")
    except Exception as e:
        print(f"Failed: {e}")

    # Case 2: Invalid cutoff (Nyquist or higher)
    cutoff = 24000
    Wn = cutoff / (fs / 2)
    print(f"Invalid case: cutoff={cutoff}, fs={fs}, Wn={Wn}")
    try:
        scipy.signal.ellip(6, 0.1, 60, Wn, btype="low", output="sos")
        print("Success.")
    except Exception as e:
        print(f"Failed (Expected): {e}")

    # Case 3: Slightly above Nyquist (Roundoff errors?)
    cutoff = 24000.0000001
    Wn = cutoff / (fs / 2)
    print(f"Invalid case (Edge): cutoff={cutoff}, fs={fs}, Wn={Wn}")
    try:
        scipy.signal.ellip(6, 0.1, 60, Wn, btype="low", output="sos")
        print("Success.")
    except Exception as e:
        print(f"Failed (Expected): {e}")

if __name__ == "__main__":
    reproduction()
