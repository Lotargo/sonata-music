from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Track, UserProfile
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
import json

from .views import normalize_processing_payload

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

    def test_user_profile_created_for_new_user(self):
        user = User.objects.create_user(username='listener', password='pass')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_account_post_updates_profile(self):
        user = User.objects.create_user(username='listener', password='pass')
        self.client.force_login(user)

        response = self.client.post(reverse('account'), {
            'display_name': 'Олег Б.',
            'plan': 'pro',
            'preferred_quality': 'lossless',
            'notifications_enabled': 'on',
            'library_auto_enhance': 'on',
        })

        self.assertEqual(response.status_code, 302)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.display_name, 'Олег Б.')
        self.assertEqual(user.profile.plan, 'pro')
        self.assertEqual(user.profile.preferred_quality, 'lossless')
        self.assertTrue(user.profile.notifications_enabled)
        self.assertTrue(user.profile.library_auto_enhance)

    def test_account_ajax_post_returns_updated_profile(self):
        user = User.objects.create_user(username='listener', password='pass')
        self.client.force_login(user)

        response = self.client.post(
            reverse('account'),
            {
                'display_name': 'Listener Pro',
                'email': 'example@gmail.com',
                'plan': 'pro',
                'preferred_quality': 'balanced',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['display_name'], 'Listener Pro')
        self.assertEqual(data['plan'], 'pro')
        self.assertTrue(data['is_pro'])
        self.assertEqual(data['preferred_quality'], 'balanced')

    def test_account_ajax_post_clears_display_name_and_pro_state(self):
        user = User.objects.create_user(username='listener', password='pass')
        self.client.force_login(user)
        user.profile.display_name = 'Listener Pro'
        user.profile.plan = 'pro'
        user.profile.save()

        response = self.client.post(
            reverse('account'),
            {
                'display_name': '',
                'plan': 'standard',
                'preferred_quality': 'high',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['display_name'], 'listener')
        self.assertEqual(data['plan_label'], 'Standard')
        self.assertEqual(data['avatar_initial'], 'L')
        self.assertFalse(data['is_pro'])

    def test_guest_account_ajax_post_updates_session_profile(self):
        response = self.client.post(
            reverse('account'),
            {
                'display_name': 'lotargo',
                'email': 'guest@example.com',
                'plan': 'pro',
                'preferred_quality': 'lossless',
                'notifications_enabled': 'on',
                'library_auto_enhance': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['display_name'], 'lotargo')
        self.assertEqual(data['email'], 'guest@example.com')
        self.assertEqual(data['plan'], 'pro')
        self.assertEqual(data['plan_label'], 'Pro')
        self.assertEqual(data['avatar_initial'], 'L')
        self.assertTrue(data['is_pro'])

        session_profile = self.client.session['guest_account_profile']
        self.assertEqual(session_profile['display_name'], 'lotargo')
        self.assertEqual(session_profile['plan'], 'pro')

    def test_guest_account_session_profile_renders_after_refresh(self):
        self.client.post(
            reverse('account'),
            {
                'display_name': 'lotargo',
                'plan': 'pro',
                'preferred_quality': 'high',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        response = self.client.get(reverse('account'))
        self.assertContains(response, '<h1>lotargo</h1>', html=True)
        self.assertContains(response, '<strong data-plan-label>Pro</strong>', html=True)
        self.assertContains(response, '<span class="profile-name" data-sidebar-name>lotargo</span>', html=True)
        self.assertContains(response, '<span>Pro</span>', html=True)
        self.assertContains(response, 'value="pro" checked')

    def test_guest_account_shows_mock_registration_action(self):
        response = self.client.get(reverse('account'))
        self.assertContains(response, 'id="register-modal"')
        self.assertContains(response, 'Зарегистрироваться')

    def test_mock_registration_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse('register_mock'),
            {
                'display_name': 'Lotargo',
                'email': 'lotargo@example.com',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['display_name'], 'Lotargo')
        self.assertEqual(data['email'], 'lotargo@example.com')
        self.assertEqual(data['username'], 'lotargo')
        self.assertFalse(data['is_pro'])

        user = User.objects.get(username='lotargo')
        self.assertEqual(user.email, 'lotargo@example.com')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)

    def test_mock_registration_transfers_guest_profile_to_user_profile(self):
        self.client.post(
            reverse('account'),
            {
                'display_name': 'Guest Pro',
                'email': 'guest@example.com',
                'plan': 'pro',
                'preferred_quality': 'lossless',
                'notifications_enabled': 'on',
                'library_auto_enhance': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        response = self.client.post(
            reverse('register_mock'),
            {
                'display_name': 'Lotargo',
                'email': 'lotargo@example.com',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='lotargo')
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.display_name, 'Lotargo')
        self.assertEqual(user.profile.plan, 'pro')
        self.assertEqual(user.profile.preferred_quality, 'lossless')
        self.assertTrue(user.profile.library_auto_enhance)
        self.assertNotIn('guest_account_profile', self.client.session)

    def test_player_bar_is_rendered_only_on_index(self):
        self.assertContains(self.client.get(reverse('index')), 'id="player-bar"')
        self.assertNotContains(self.client.get(reverse('account')), 'id="player-bar"')

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

    def test_processing_payload_normalizes_ui_percent_controls(self):
        params = normalize_processing_payload({
            'mode': 'hybrid',
            'format': 'ogg',
            'sample_rate': '96000',
            'bitrate': '500k',
            'steps': '250',
            'guidance': '20',
            'batch_size': '12',
            'reverb_enabled': 'true',
            'reverb_size': '40',
            'reverb_amount': '12',
            'bass_boost': '99',
            'voice_clarity': '-9',
            'compressor_amount': '65',
            'stereo_width': '150',
        })

        self.assertEqual(params['mode'], 'hybrid')
        self.assertEqual(params['format'], 'ogg')
        self.assertEqual(params['sample_rate'], 96000)
        self.assertEqual(params['bitrate'], '500k')
        self.assertEqual(params['steps'], 200)
        self.assertEqual(params['guidance'], 15.0)
        self.assertEqual(params['batch_size'], 8)
        self.assertEqual(params['dsp_params']['stereo_width'], 1.5)
        self.assertEqual(params['dsp_params']['compressor_amount'], 0.65)
        self.assertEqual(params['dsp_params']['reverb_size'], 0.4)
        self.assertEqual(params['dsp_params']['reverb_amount'], 0.12)
        self.assertEqual(params['dsp_params']['bass_boost'], 10.0)
        self.assertEqual(params['dsp_params']['voice_clarity'], -5.0)
        self.assertTrue(params['dsp_params']['reverb_enabled'])

    def test_process_endpoint_passes_normalized_payload_to_thread(self):
        payload = {
            'title': 'Processed title',
            'artist': 'Processed artist',
            'mode': 'ai',
            'format': 'mp3',
            'sample_rate': '48000',
            'bitrate': '500k',
            'quality_preset': 'high',
            'steps': '100',
            'guidance': '4.2',
            'seed': '123',
            'batch_size': '4',
            'stereo_width': '125',
            'compressor_amount': '55',
        }

        with patch('music.views.threading.Thread') as thread_cls:
            response = self.client.post(
                reverse('process_track', args=[self.track.id]),
                data=json.dumps(payload),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.track.refresh_from_db()
        self.assertEqual(self.track.title, 'Processed title')
        self.assertEqual(self.track.artist, 'Processed artist')

        thread_cls.assert_called_once()
        thread_cls.return_value.start.assert_called_once()
        _, params = thread_cls.call_args.kwargs['args']
        self.assertEqual(params['mode'], 'ai')
        self.assertEqual(params['format'], 'mp3')
        self.assertEqual(params['bitrate'], '320k')
        self.assertEqual(params['steps'], 100)
        self.assertEqual(params['guidance'], 4.2)
        self.assertEqual(params['seed'], 123)
        self.assertEqual(params['batch_size'], 4)
        self.assertEqual(params['dsp_params']['stereo_width'], 1.25)
        self.assertEqual(params['dsp_params']['compressor_amount'], 0.55)
