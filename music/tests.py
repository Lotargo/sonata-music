from django.test import TestCase, Client
from django.urls import reverse
from .models import Track
from django.core.files.uploadedfile import SimpleUploadedFile

class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Mock file for file field
        self.track = Track.objects.create(
            title="Test Track",
            artist="Test Artist",
            audio_file=SimpleUploadedFile("test.mp3", b"content")
        )

    def test_history_view(self):
        response = self.client.get(reverse('history'))
        self.assertEqual(response.status_code, 200)

    def test_likes_view(self):
        response = self.client.get(reverse('likes'))
        self.assertEqual(response.status_code, 200)

    def test_account_view(self):
        response = self.client.get(reverse('account'))
        self.assertEqual(response.status_code, 200)

    def test_toggle_like(self):
        response = self.client.post(reverse('toggle_like', args=[self.track.id]))
        self.assertEqual(response.status_code, 200)
        self.track.refresh_from_db()
        self.assertTrue(self.track.is_liked)

    def test_record_play(self):
        response = self.client.post(reverse('record_play', args=[self.track.id]))
        self.assertEqual(response.status_code, 200)
        self.track.refresh_from_db()
        self.assertEqual(self.track.play_count, 1)
