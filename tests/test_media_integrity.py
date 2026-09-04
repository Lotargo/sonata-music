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

    def test_ranged_media_serve_full_and_partial(self):
        # Create a temporary audio test file in MEDIA_ROOT
        test_rel = "test_audio_sample.mp3"
        test_abs = Path(settings.MEDIA_ROOT) / test_rel
        test_data = b"0123456789ABCDEF0123456789ABCDEF"  # 32 bytes
        test_abs.write_bytes(test_data)

        try:
            # 1. Full content request
            resp_full = self.client.get(f'/media/{test_rel}')
            self.assertEqual(resp_full.status_code, 200)
            self.assertEqual(resp_full.headers.get('Accept-Ranges'), 'bytes')
            self.assertEqual(b"".join(resp_full.streaming_content), test_data)

            # 2. Ranged request (first 10 bytes: bytes=0-9)
            resp_part = self.client.get(f'/media/{test_rel}', HTTP_RANGE='bytes=0-9')
            self.assertEqual(resp_part.status_code, 206)
            self.assertEqual(resp_part.headers.get('Accept-Ranges'), 'bytes')
            self.assertEqual(resp_part.headers.get('Content-Range'), 'bytes 0-9/32')
            self.assertEqual(resp_part.headers.get('Content-Length'), '10')
            self.assertEqual(b"".join(resp_part.streaming_content), b"0123456789")

            # 3. Ranged request to end (bytes=16-)
            resp_end = self.client.get(f'/media/{test_rel}', HTTP_RANGE='bytes=16-')
            self.assertEqual(resp_end.status_code, 206)
            self.assertEqual(resp_end.headers.get('Content-Range'), 'bytes 16-31/32')
            self.assertEqual(b"".join(resp_end.streaming_content), test_data[16:])

            # 4. Out of bounds range
            resp_oob = self.client.get(f'/media/{test_rel}', HTTP_RANGE='bytes=100-200')
            self.assertEqual(resp_oob.status_code, 416)

            # 5. Non-existent file
            resp_404 = self.client.get('/media/does_not_exist_file.mp3')
            self.assertEqual(resp_404.status_code, 404)
        finally:
            if test_abs.exists():
                test_abs.unlink()

