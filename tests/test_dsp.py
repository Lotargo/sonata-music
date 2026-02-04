import unittest
import os
import soundfile as sf
import numpy as np
from app.services.dsp import dsp


class TestStudioDSP(unittest.TestCase):
    def setUp(self):
        self.test_input = "test_input.wav"
        self.test_output = "test_output.wav"

        # Create a dummy silent wav file
        sr = 48000
        duration = 1.0  # seconds
        data = np.zeros((int(sr * duration), 2))  # Stereo silence
        sf.write(self.test_input, data, sr)

    def tearDown(self):
        if os.path.exists(self.test_input):
            os.remove(self.test_input)
        if os.path.exists(self.test_output):
            os.remove(self.test_output)

    def test_dsp_presets(self):
        # Test all presets
        presets = ["mastering", "clear", "warm", "punchy"]
        for preset in presets:
            try:
                dsp.process(self.test_input, self.test_output, preset_name=preset)
                self.assertTrue(os.path.exists(self.test_output))
                # Check output format
                data, sr = sf.read(self.test_output)
                self.assertEqual(sr, 48000)
                # Cleanup for next loop
                os.remove(self.test_output)
            except Exception as e:
                self.fail(f"DSP failed for preset {preset}: {e}")

    def test_resampling(self):
        # Create 44.1k file
        sr = 44100
        data = np.zeros((int(sr * 1.0), 2))
        sf.write(self.test_input, data, sr)

        # Process to 48k
        dsp.process(self.test_input, self.test_output, sample_rate=48000)

        data, sr_out = sf.read(self.test_output)
        self.assertEqual(sr_out, 48000)


if __name__ == "__main__":
    unittest.main()
