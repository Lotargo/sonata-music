import unittest
import numpy as np
from music.services.dsp import StudioDSP


class TestPhaseADspRepair(unittest.TestCase):
    def setUp(self):
        self.dsp = StudioDSP()
        self.sr = 48000
        self.duration = 0.5
        self.t = np.linspace(0, self.duration, int(self.sr * self.duration), endpoint=False)

    def test_new_studio_presets_registered(self):
        expected_presets = [
            "mastering", "punchy", "deep_bass", "clear", "warm", "stealth",
            "vocal_polish", "club_bass", "broadcast", "tape_warmth", "natural_air",
            "music_fix", "audio_repair"
        ]
        for preset in expected_presets:
            self.assertIn(preset, self.dsp.preset_configs, f"Preset '{preset}' should be registered in StudioDSP")

    def test_apply_music_fix(self):
        # Generate signal with excessive 350 Hz mud
        clean_sine = 0.3 * np.sin(2 * np.pi * 1000 * self.t)
        mud_sine = 0.5 * np.sin(2 * np.pi * 350 * self.t)
        audio = np.stack([clean_sine + mud_sine, clean_sine + mud_sine]).astype(np.float32)

        fixed = self.dsp.apply_music_fix(audio, self.sr)
        self.assertEqual(fixed.shape, audio.shape)
        self.assertFalse(np.isnan(fixed).any())

        # The energy around 350Hz should be reduced compared to input
        fft_orig = np.abs(np.fft.rfft(audio[0]))
        fft_fixed = np.abs(np.fft.rfft(fixed[0]))
        freqs = np.fft.rfftfreq(len(audio[0]), 1 / self.sr)
        mud_bin = np.argmin(np.abs(freqs - 350))

        self.assertLess(fft_fixed[mud_bin], fft_orig[mud_bin])

    def test_apply_audio_repair_dc_offset(self):
        # Audio with severe DC bias
        audio = 0.3 * np.sin(2 * np.pi * 440 * self.t) + 0.25
        audio = np.stack([audio, audio]).astype(np.float32)

        repaired = self.dsp.apply_audio_repair(audio, self.sr, remove_dc=True, declip=False, declick=False)
        # DC offset should be virtually zero
        dc_mean = np.mean(repaired)
        self.assertAlmostEqual(dc_mean, 0.0, places=2)

    def test_apply_audio_repair_declipping(self):
        # Generate hard-clipped sine wave
        sine = 1.8 * np.sin(2 * np.pi * 200 * self.t)
        clipped = np.clip(sine, -0.999, 0.999)
        audio = np.stack([clipped, clipped]).astype(np.float32)

        # Confirm there are clipped samples
        self.assertTrue((np.abs(audio) >= 0.99).any())

        repaired = self.dsp.apply_audio_repair(audio, self.sr, remove_dc=False, declip=True, declick=False)
        self.assertEqual(repaired.shape, audio.shape)
        self.assertFalse(np.isnan(repaired).any())

    def test_apply_audio_repair_declicking(self):
        # Add artificial impulse spike (click)
        audio = 0.4 * np.sin(2 * np.pi * 440 * self.t)
        click_idx = 1000
        audio[click_idx] = 1.0  # abrupt spike click
        audio = np.stack([audio, audio]).astype(np.float32)

        repaired = self.dsp.apply_audio_repair(audio, self.sr, remove_dc=False, declip=False, declick=True)
        # Spike should be suppressed significantly
        self.assertLess(np.abs(repaired[0, click_idx]), 0.8)


if __name__ == "__main__":
    unittest.main()
