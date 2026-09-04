from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Track, UserProfile
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
import json
import tempfile
from pathlib import Path
from django.test import override_settings

from .views import normalize_processing_payload

class ViewTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_directory.cleanup)
        self.addCleanup(self.media_override.disable)

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

    def test_upload_modal_supports_close_button_and_backdrop(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'onclick="closeUploadModal()"')
        self.assertContains(response, 'onclick="handleUploadModalBackdrop(event)"')
        self.assertContains(response, 'class="upload-note-icon w-8 h-8"')
        self.assertContains(response, 'music/js/upload.js?v=7')
        self.assertContains(response, 'music/js/upload-modal-copy.js?v=5')

    def test_delete_uses_custom_confirmation_modal(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'id="delete-confirm-modal"')
        self.assertContains(response, 'id="delete-confirm-track-name"')
        self.assertContains(response, 'onclick="confirmTrackDeletion()"')
        self.assertContains(response, 'music/css/style.css?v=62')
        self.assertContains(response, 'music/js/player.js?v=19')
        self.assertNotContains(response, "confirm('Удалить этот трек?')")

    def test_track_play_button_is_rendered_inside_cover(self):
        response = self.client.get(reverse('index'))
        html = response.content.decode()
        cover_start = html.index('<div class="row-cover">')
        cover_end = html.index('</div>', cover_start)
        play_button = html.index('class="row-play play-btn"', cover_start)

        self.assertLess(play_button, cover_end)
        self.assertContains(response, 'music/css/style.css?v=62')
        self.assertContains(response, 'music/js/player.js?v=19')

    def test_player_equalizer_has_dedicated_modal_and_audio_controls(self):
        response = self.client.get(reverse('index'))

        self.assertContains(response, 'id="equalizer-trigger"')
        self.assertContains(response, 'onclick="openEqualizer()"')
        self.assertContains(response, 'id="equalizer-modal"')
        self.assertContains(response, 'id="equalizer-band-grid"')
        self.assertContains(response, 'id="equalizer-spectrum-canvas"')
        self.assertContains(response, 'id="equalizer-bass-enabled"')
        self.assertContains(response, 'id="equalizer-clarity-enabled"')
        self.assertContains(response, 'id="equalizer-compressor-enabled"')
        self.assertContains(response, 'music/js/equalizer.js?v=2')
        self.assertNotContains(response, 'onclick="if(currentTrackId) openDetails(currentTrackId);"')

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

    def test_toggle_like_and_dislike_mutual_exclusion(self):
        track = Track.objects.create(
            title="Feedback Track",
            artist="Listener",
            audio_file=SimpleUploadedFile("feedback.mp3", b"dummy")
        )

        # 1. Like track
        res = self.client.post(reverse('toggle_like', args=[track.id]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['is_liked'])
        self.assertFalse(data['is_disliked'])

        track.refresh_from_db()
        self.assertTrue(track.is_liked)
        self.assertFalse(track.is_disliked)

        # 2. Dislike track (should clear like)
        res = self.client.post(reverse('toggle_dislike', args=[track.id]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data['is_liked'])
        self.assertTrue(data['is_disliked'])

        track.refresh_from_db()
        self.assertFalse(track.is_liked)
        self.assertTrue(track.is_disliked)

        # 3. Toggle dislike again (un-dislike)
        res = self.client.post(reverse('toggle_dislike', args=[track.id]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data['is_liked'])
        self.assertFalse(data['is_disliked'])

        track.refresh_from_db()
        self.assertFalse(track.is_liked)
        self.assertFalse(track.is_disliked)


class StagedUploadTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media_directory.cleanup()

    def upload_draft(self, filename='draft.wav'):
        with (
            patch('music.views.extract_metadata', return_value={
                'title': 'Draft title',
                'artist': 'Draft artist',
                'cover_path': None,
            }),
            patch('music.services.analyzer.analyze_track_acoustics', return_value={
                'bpm': 120.0,
                'musical_key': 'C major',
                'spectral_centroid': 2400.0,
                'duration': 30.0,
            }),
        ):
            return self.client.post(
                reverse('upload'),
                {'audio_file': SimpleUploadedFile(filename, b'draft-audio')},
            )

    def test_upload_is_staged_without_creating_library_record(self):
        response = self.upload_draft()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Track.objects.count(), 0)
        self.assertIn('upload_token', response.json())
        self.assertNotIn('id', response.json())
        self.assertEqual(self.client.get(reverse('library_api')).json(), [])
        self.assertTrue(any(Path(self.media_directory.name, 'pending_uploads').rglob('draft.wav')))

    def test_closing_modal_discards_staged_file_without_database_cleanup(self):
        upload_response = self.upload_draft()
        token = upload_response.json()['upload_token']

        response = self.client.delete(
            reverse('cancel_staged_upload'),
            data=json.dumps({'upload_token': token}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Track.objects.count(), 0)
        pending_root = Path(self.media_directory.name, 'pending_uploads')
        self.assertFalse(pending_root.exists() and any(pending_root.rglob('*')))

    def test_processing_modes_create_track_only_when_processing_starts(self):
        for mode in ('dsp', 'ai', 'hybrid'):
            with self.subTest(mode=mode):
                upload_response = self.upload_draft(f'{mode}.wav')
                token = upload_response.json()['upload_token']
                count_before = Track.objects.count()

                with patch('music.views.threading.Thread') as thread_cls:
                    response = self.client.post(
                        reverse('process_staged_upload'),
                        data=json.dumps({
                            'upload_token': token,
                            'title': f'{mode} title',
                            'artist': 'Test artist',
                            'mode': mode,
                            'format': 'wav',
                        }),
                        content_type='application/json',
                    )

                self.assertEqual(response.status_code, 201)
                self.assertEqual(Track.objects.count(), count_before + 1)
                track = Track.objects.get(id=response.json()['id'])
                self.assertEqual(track.status, 'processing')
                self.assertEqual(track.title, f'{mode} title')
                self.assertTrue(track.has_audio_file)
                thread_cls.assert_called_once()
                thread_cls.return_value.start.assert_called_once()
                _, params = thread_cls.call_args.kwargs['args']
                self.assertEqual(params['mode'], mode)

    def test_failed_thread_start_does_not_leave_library_record(self):
        upload_response = self.upload_draft()
        token = upload_response.json()['upload_token']

        with patch('music.views.threading.Thread') as thread_cls:
            thread_cls.return_value.start.side_effect = RuntimeError('thread unavailable')
            response = self.client.post(
                reverse('process_staged_upload'),
                data=json.dumps({
                    'upload_token': token,
                    'mode': 'dsp',
                    'format': 'wav',
                }),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(Track.objects.count(), 0)
        self.assertEqual(self.client.get(reverse('library_api')).json(), [])

    def test_processing_requires_staged_upload_token(self):
        response = self.client.post(
            reverse('process_staged_upload'),
            data=json.dumps({'mode': 'dsp', 'format': 'wav'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Track.objects.count(), 0)

