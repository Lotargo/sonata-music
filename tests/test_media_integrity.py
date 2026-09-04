import os
from pathlib import Path
from django.test import TestCase, Client
from django.core.management import call_command
from django.conf import settings
from music.models import Track


class MediaIntegrityTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_favicon_endpoint(self):
        response = self.client.get('/favicon.ico')
        self.assertEqual(response.status_code, 200)
        self.assertIn('image/svg+xml', response.headers.get('Content-Type', ''))
        self.assertIn('<svg', response.content.decode('utf-8'))

    def test_track_safe_media_properties_missing_files(self):
        track = Track.objects.create(
            title="Ghost Track",
            artist="Ghost Artist",
            audio_file="uploads/non_existent_ghost.mp3",
            cover_image="covers/non_existent_ghost.jpg",
            processed_file="processed/non_existent_ghost_dsp.wav",
        )
        self.assertFalse(track.has_cover)
        self.assertIsNone(track.cover_url)
        self.assertFalse(track.has_audio_file)
        self.assertFalse(track.has_processed_file)
        self.assertFalse(track.is_available)

    def test_track_safe_media_properties_existing_files(self):
        # Create a temporary dummy file in MEDIA_ROOT
        cover_rel = "covers/test_dummy_cover.jpg"
        cover_abs = Path(settings.MEDIA_ROOT) / cover_rel
        cover_abs.parent.mkdir(parents=True, exist_ok=True)
        cover_abs.write_bytes(b"dummy image data")

        try:
            track = Track.objects.create(
                title="Real Track",
                artist="Real Artist",
                cover_image=cover_rel,
            )
            self.assertTrue(track.has_cover)
            self.assertIsNotNone(track.cover_url)
            self.assertIn('covers/test_dummy_cover.jpg', track.cover_url)
        finally:
            if cover_abs.exists():
                cover_abs.unlink()

    def test_library_payload_does_not_leak_dead_cover_url(self):
        Track.objects.create(
            title="Dead Cover Track",
            artist="Dead Artist",
            cover_image="covers/dead_cover_never_existed.jpg",
        )
        response = self.client.get('/library/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        matching = [t for t in data if t['title'] == 'Dead Cover Track']
        self.assertEqual(len(matching), 1)
        self.assertIsNone(matching[0]['cover_path'])
        self.assertFalse(matching[0]['has_cover'])

    def test_cleanup_missing_media_command(self):
        track = Track.objects.create(
            title="Cleanup Target",
            artist="Cleanup Artist",
            cover_image="covers/will_be_cleared.jpg",
        )
        self.assertIsNotNone(track.cover_image)

        # Call cleanup command
        call_command('cleanup_missing_media')

        track.refresh_from_db()
        self.assertFalse(bool(track.cover_image))
