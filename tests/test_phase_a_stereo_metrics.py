import unittest
import numpy as np
import soundfile as sf
import tempfile
import os
from music.services.metrics import MetricsService


class TestPhaseAStereoMetrics(unittest.TestCase):
    def setUp(self):
        self.metrics_service = MetricsService()
        self.sr = 48000
        self.duration = 1.0  # 1 second
        self.t = np.linspace(0, self.duration, int(self.sr * self.duration), endpoint=False)

    def test_mono_metrics(self):
        # 1 kHz mono sine wave
        mono_data = 0.5 * np.sin(2 * np.pi * 1000 * self.t)
        res = self.metrics_service._calculate_metrics(mono_data)
        
        self.assertIn("stereo_correlation", res)
        self.assertEqual(res["stereo_correlation"], 1.0)
        self.assertEqual(res["stereo_width_ratio"], 0.0)
        self.assertIn("rms_side_db", res)
        self.assertLess(res["rms_side_db"], -90.0)

    def test_identical_stereo_is_mono(self):
        # Left and Right are identical -> correlation should be 1.0, side signal silence
        sine = 0.5 * np.sin(2 * np.pi * 1000 * self.t)
        stereo_data = np.stack([sine, sine], axis=1)
        res = self.metrics_service._calculate_metrics(stereo_data)

        self.assertAlmostEqual(res["stereo_correlation"], 1.0, places=2)
        self.assertLess(res["rms_side_db"], -90.0)
        self.assertAlmostEqual(res["stereo_width_ratio"], 0.0, places=2)
        self.assertAlmostEqual(res["peak_l_db"], res["peak_r_db"], places=1)

    def test_out_of_phase_stereo(self):
        # Left and Right are inverted -> correlation should be -1.0, mid signal silence
        left = 0.5 * np.sin(2 * np.pi * 1000 * self.t)
        right = -0.5 * np.sin(2 * np.pi * 1000 * self.t)
        stereo_data = np.stack([left, right], axis=1)
        res = self.metrics_service._calculate_metrics(stereo_data)

        self.assertAlmostEqual(res["stereo_correlation"], -1.0, places=2)
        self.assertLess(res["rms_mid_db"], -90.0)
        self.assertGreater(res["stereo_width_ratio"], 10.0)

    def test_wide_stereo_independent_channels(self):
        # Independent Left and Right signals (uncorrelated)
        left = 0.5 * np.sin(2 * np.pi * 440 * self.t)
        right = 0.5 * np.cos(2 * np.pi * 880 * self.t)
        stereo_data = np.stack([left, right], axis=1)
        res = self.metrics_service._calculate_metrics(stereo_data)

        self.assertAlmostEqual(res["stereo_correlation"], 0.0, delta=0.1)
        self.assertGreater(res["rms_side_db"], -20.0)
        self.assertGreater(res["stereo_width_ratio"], 0.5)

    def test_generate_report_includes_stereo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_path = os.path.join(tmpdir, "orig.wav")
            proc_path = os.path.join(tmpdir, "proc.wav")
            out_base = os.path.join(tmpdir, "report")

            # Create test wavs
            left = 0.4 * np.sin(2 * np.pi * 440 * self.t)
            right = 0.4 * np.sin(2 * np.pi * 440 * self.t + 0.3)
            data = np.stack([left, right], axis=1).astype(np.float32)

            sf.write(orig_path, data, self.sr)
            sf.write(proc_path, data * 1.1, self.sr)

            json_path = self.metrics_service.generate_report(orig_path, proc_path, out_base)
            self.assertIsNotNone(json_path)
            self.assertTrue(os.path.exists(json_path))

            import json
            with open(json_path, "r") as f:
                report = json.load(f)

            self.assertIn("stereo_correlation", report["original"])
            self.assertIn("stereo_correlation", report["processed"])
            self.assertIn("rms_side_db", report["original"])
            self.assertIn("peak_l_db", report["original"])
            self.assertIn("peak_r_db", report["original"])


if __name__ == "__main__":
    unittest.main()
