
import numpy as np
import torch
from app.services.upscaler import safe_lowpass_filter

def verify_exact_signature():
    print("Verifying safe_lowpass_filter with exact AudioSR signature...")

    fs = 48000
    cutoff = 20000
    order = 6
    ftype = 'ellip'

    # Case 1: Exact positional matching audiosr call: (x, highcut, fs, order, ftype)
    try:
        print("Testing exact positional args...")
        wf = np.zeros((1, 1024))
        # def lowpass_filter(x, highcut, fs, order, ftype):
        safe_lowpass_filter(wf, cutoff, fs, order, ftype)
        print("Success: Exact positional args.")
    except Exception as e:
        print(f"Failed exact positional: {e}")
        raise e

    # Case 2: Named arguments
    try:
        print("Testing named args...")
        wf = np.zeros((1, 1024))
        safe_lowpass_filter(x=wf, highcut=cutoff, fs=fs, order=order, ftype=ftype)
        print("Success: Named args.")
    except Exception as e:
        print(f"Failed named args: {e}")
        raise e

if __name__ == "__main__":
    verify_exact_signature()
