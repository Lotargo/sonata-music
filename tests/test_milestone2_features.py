import os
import sys
import unittest
from pathlib import Path
import numpy as np

# Ensure django setup
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import TestCase, RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from music.models import Track
from music.views import track_payload
from music.services.analyzer import (
    analyze_track_acoustics,
    apply_analog_drift,
    trim_silence_lossless,
    estimate_musical_key,
)


class Milestone2AcousticsTestCase(TestCase):
    def setUp(self):
        self.sample_album_dir = Path('.samples/Album 1')
        self.sample_file = self.sample_album_dir / '00 - Tape 00_ Toluca Overlook (Prologue).wav'

    def test_key_estimation_profiles(self):
        """Test the Krumhansl-Schmuckler key estimation with synthetic C major profile."""
        # Simulated C Major chroma (strong C=0, E=4, G=7)
        c_major_chroma = np.array([6.0, 1.0, 2.0, 1.0, 4.5, 3.5, 1.0, 5.0, 1.0, 2.5, 1.0, 1.5])
        key, conf = estimate_musical_key(c_major_chroma)
        self.assertEqual(key, 'C Major')
        self.assertGreater(conf, 0.7)

    def test_analog_drift(self):
        """Test that analog drift applies subtle time stretch without NaNs."""
        sr = 22050
        # 1 second stereo test wave
        t = np.linspace(0, 1, sr, endpoint=False)
        tone = (np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        stereo = np.stack([tone, tone])

        drifted = apply_analog_drift(stereo, drift_rate=1.002)
        self.assertIsInstance(drifted, np.ndarray)
        self.assertEqual(drifted.ndim, 2)
        self.assertEqual(drifted.shape[0], 2)
        self.assertFalse(np.isnan(drifted).any())
        self.assertFalse(np.isinf(drifted).any())

    def test_acoustic_analysis_on_real_sample(self):
        """Run acoustic analysis on real sample track from Album 1."""
        if not self.sample_file.exists():
            self.skipTest("Sample audio file not found in .samples/Album 1")

        result = analyze_track_acoustics(self.sample_file, max_duration=60.0)
        self.assertIsNotNone(result['bpm'])
        self.assertGreaterEqual(result['bpm'], 50.0)
        self.assertLessEqual(result['bpm'], 220.0)

        self.assertIsNotNone(result['musical_key'])
        self.assertTrue(result['musical_key'].endswith(('Major', 'Minor')))

        self.assertIsNotNone(result['spectral_centroid'])
        self.assertGreater(result['spectral_centroid'], 100.0)

        self.assertIsNotNone(result['duration'])
        self.assertGreater(result['duration'], 60.0)

    def test_track_model_acoustic_fields_and_payload(self):
        """Verify Track model saves and returns bpm, musical_key, spectral_centroid."""
        dummy_audio = SimpleUploadedFile("test_song.wav", b"RIFF....WAVEfmt ....data....", content_type="audio/wav")
        track = Track.objects.create(
            title="Toluca Overlook",
            artist="Test Artist",
            audio_file=dummy_audio,
            bpm=136.0,
            musical_key="F Minor",
            spectral_centroid=768.3,
            duration=134.4,
            status="completed"
        )

        payload = track_payload(track)
        self.assertEqual(payload['bpm'], 136.0)
        self.assertEqual(payload['musical_key'], "F Minor")
        self.assertEqual(payload['spectral_centroid'], 768.3)
        self.assertEqual(payload['duration'], 134.4)


if __name__ == '__main__':
    unittest.main()
