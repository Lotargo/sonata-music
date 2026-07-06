import os
import threading
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.conf import settings
from django.core.files.storage import default_storage
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model, login
from django.contrib.auth.backends import ModelBackend
from django.utils.text import slugify

from .account_state import account_payload, clear_guest_profile, get_account_profile, get_guest_profile_data, save_account_profile
from .models import Track, UserProfile
from .services.upscaler import upscaler
from .services.metadata import extract_metadata

logger = logging.getLogger(__name__)

PROCESSING_MODES = {'ai', 'dsp', 'hybrid', 'restoration'}
TARGET_FORMATS = {'wav', 'mp3', 'flac', 'ogg'}
TARGET_SAMPLE_RATES = {44100, 48000, 96000}
LOSSY_BITRATES = {'128k', '192k', '256k', '320k', '500k'}
LOSSLESS_DEPTHS = {'16-bit', '24-bit', '32-bit'}
QUALITY_STEPS = {
    'fast': 25,
    'balanced': 50,
    'high': 100,
}


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def as_int(value, default, minimum=None, maximum=None):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default

    if minimum is not None and maximum is not None:
        return clamp(number, minimum, maximum)
    if minimum is not None:
        return max(minimum, number)
    if maximum is not None:
        return min(maximum, number)
    return number


def as_float(value, default, minimum=None, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default

    if minimum is not None and maximum is not None:
        return clamp(number, minimum, maximum)
    if minimum is not None:
        return max(minimum, number)
    if maximum is not None:
        return min(maximum, number)
    return number


def as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def normalized_ratio(value, default, maximum=1.0):
    number = as_float(value, default)
    if maximum <= 1.0 and number > 1.0:
        number = number / 100.0
    elif maximum > 1.0 and number > maximum:
        number = number / 100.0
    return clamp(number, 0.0, maximum)


def normalize_processing_payload(data):
    mode = data.get('mode', 'ai')
    if mode not in PROCESSING_MODES:
        mode = 'ai'

    target_format = str(data.get('format', 'wav')).lower()
    if target_format not in TARGET_FORMATS:
        target_format = 'wav'

    sample_rate = as_int(data.get('sample_rate'), 48000)
    if sample_rate not in TARGET_SAMPLE_RATES:
        sample_rate = 48000

    bitrate_default = '320k' if target_format in {'mp3', 'ogg'} else '24-bit'
    bitrate = str(data.get('bitrate') or bitrate_default)
    if target_format in {'mp3', 'ogg'}:
        bitrate = bitrate if bitrate in LOSSY_BITRATES else '320k'
        if target_format == 'mp3' and bitrate == '500k':
            bitrate = '320k'
    else:
        bitrate = bitrate if bitrate in LOSSLESS_DEPTHS else '24-bit'

    preset_steps = QUALITY_STEPS.get(data.get('quality_preset'))
    steps = as_int(data.get('steps'), preset_steps or 50, 1, 200)

    dsp_params = {
        'reverb_enabled': as_bool(data.get('reverb_enabled')),
        'reverb_size': normalized_ratio(data.get('reverb_size'), 0.5),
        'reverb_amount': normalized_ratio(data.get('reverb_amount'), 0.3),
        'bass_boost': as_float(data.get('bass_boost'), 0.0, -10.0, 10.0),
        'voice_clarity': as_float(data.get('voice_clarity'), 0.0, -5.0, 10.0),
        'compressor_amount': normalized_ratio(data.get('compressor_amount'), 0.5),
        'stereo_width': normalized_ratio(data.get('stereo_width'), 1.0, 2.0),
    }

    return {
        'mode': mode,
        'format': target_format,
        'sample_rate': sample_rate,
        'bitrate': bitrate,
        'steps': steps,
        'guidance': as_float(data.get('guidance'), 3.5, 1.0, 15.0),
        'seed': as_int(data.get('seed'), 42, 0, 2147483647),
        'batch_size': as_int(data.get('batch_size'), 2, 1, 8),
        'dsp_preset': data.get('dsp_preset') or 'mastering',
        'dsp_params': dsp_params,
    }


def unique_mock_username(seed):
    User = get_user_model()
    base = slugify(seed or '', allow_unicode=False) or 'listener'
    base = base[:24].strip('-_') or 'listener'
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f'{base}-{suffix}'
    return username

def index(request):
    tracks = Track.objects.all().order_by('-created_at')
    featured_track = (
        Track.objects.filter(cover_image__isnull=False).order_by('-created_at').first()
        or Track.objects.filter(status='completed').order_by('-created_at').first()
        or tracks.first()
    )
    liked_tracks = list(Track.objects.filter(is_liked=True).order_by('-created_at')[:4])
    history_tracks = list(Track.objects.filter(play_count__gt=0).order_by('-created_at')[:4])

    context = {
        'tracks': tracks,
        'featured_track': featured_track,
        'liked_tracks': liked_tracks,
        'history_tracks': history_tracks,
        'liked_count': Track.objects.filter(is_liked=True).count(),
        'history_count': Track.objects.filter(play_count__gt=0).count(),
    }
    return render(request, 'music/index.html', context)

@require_http_methods(["GET", "POST"])
def upload(request):
    # If GET, render the upload page (though we are moving to modal, keeping this for fallback)
    if request.method == 'GET':
        return render(request, 'music/upload.html')

    # POST Logic
    if 'audio_file' not in request.FILES:
        return JsonResponse({"error": "No file part"}, status=400)

    audio_file = request.FILES['audio_file']
    if not audio_file.name:
        return JsonResponse({"error": "No selected file"}, status=400)

    # Save initial track to get a file path
    # We create a pending track
    track = Track(
        audio_file=audio_file,
        status='pending',
        title=audio_file.name, # Temporary title
        artist='Unknown Artist'
    )
    track.save()

    # Extract metadata
    # track.audio_file.path gives the absolute path
    try:
        meta = extract_metadata(track.audio_file.path)

        if meta.get('title'):
            track.title = meta['title']
        if meta.get('artist'):
            track.artist = meta['artist']
        if meta.get('cover_path'):
            # Assign relative path to ImageField
            track.cover_image = meta['cover_path']

        track.save()

        return JsonResponse({
            'id': track.id,
            'title': track.title,
            'artist': track.artist,
            'cover_url': track.cover_image.url if track.cover_image else None,
            'audio_url': track.audio_file.url,
            'filename': os.path.basename(track.audio_file.name)
        }, status=201)

    except Exception as e:
        logger.error(f"Error in upload/metadata extraction: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def run_upscaling_thread(track_id, params):
    """
    Background thread wrapper for upscaling.
    """
    try:
        # Re-fetch track in this thread (avoid passing model instance across threads)
        # We need to manage DB connection in threads if not using standard Django workers,
        # but for simple threading, ensuring a fresh query usually works if connection is persistent or auto-managed.
        # Django closes connections at end of request, so new thread needs to handle it.
        # Actually, simpler to just pass IDs and let service handle logic, but service assumes paths.

        from .models import Track # Local import to avoid circular issues
        track = Track.objects.get(id=track_id)

        # Prepare paths
        input_path = track.audio_file.path

        # Generate output filename
        base, ext = os.path.splitext(os.path.basename(input_path))
        mode = params.get('mode', 'ai')
        target_format = params.get('format', 'wav')

        suffix_map = {
            'ai': '_ai',
            'dsp': '_dsp',
            'hybrid': '_hybrid',
            'restoration': '_restored'
        }
        suffix = suffix_map.get(mode, '_ai')
        output_filename = f"{base}{suffix}.{target_format}"

        # We save processed files to MEDIA_ROOT/processed/
        processed_dir = os.path.join(settings.MEDIA_ROOT, 'processed')
        os.makedirs(processed_dir, exist_ok=True)
        output_path = os.path.join(processed_dir, output_filename)

        track.status = 'processing'
        track.target_format = target_format
        track.target_bitrate = params.get('bitrate')
        track.save()

        # Call Service
        success = upscaler.process_track(
            input_path=input_path,
            output_path=output_path,
            mode=mode,
            ddim_steps=int(params.get('steps', 50)),
            guidance_scale=float(params.get('guidance', 3.5)),
            seed=int(params.get('seed', 42)),
            batch_size=int(params.get('batch_size', 2)),
            target_format=target_format,
            target_sample_rate=int(params.get('sample_rate', 48000)),
            target_bitrate=params.get('bitrate', '320k'),
            dsp_preset=params.get('dsp_preset', 'mastering'),
            dsp_params=params.get('dsp_params')
        )

        if success:
            track.status = 'completed'
            # Save relative path to FileField
            track.processed_file.name = os.path.join('processed', output_filename)
        else:
            track.status = 'failed'

        track.save()

    except Exception as e:
        logger.error(f"Processing failed for track {track_id}: {e}")
        # Try to update status
        try:
            t = Track.objects.get(id=track_id)
            t.status = 'failed'
            t.save()
        except:
            pass

@require_POST
def process_track(request, track_id):
    track = get_object_or_404(Track, id=track_id)

    if track.status == 'processing':
        return JsonResponse({'error': 'Track is already processing'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Update track info if provided
    if 'title' in data:
        track.title = data['title']
    if 'artist' in data:
        track.artist = data['artist']
    track.save()

    params = normalize_processing_payload(data)

    # Start thread
    thread = threading.Thread(target=run_upscaling_thread, args=(track.id, params))
    thread.start()

    return JsonResponse({'message': 'Processing started', 'status': 'processing'})

def history(request):
    tracks = Track.objects.filter(play_count__gt=0).order_by('-play_count', '-created_at')
    return render(request, 'music/history.html', {'tracks': tracks})

def likes(request):
    tracks = Track.objects.filter(is_liked=True).order_by('-created_at')
    return render(request, 'music/likes.html', {'tracks': tracks})

@require_http_methods(["GET", "POST"])
def account(request):
    if request.method == 'POST':
        account_profile = save_account_profile(request)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(account_payload(account_profile))
        return redirect('account')

    tracks = Track.objects.all()
    context = {
        'tracks_count': tracks.count(),
        'processed_count': tracks.filter(status='completed').count(),
        'liked_count': tracks.filter(is_liked=True).count(),
        'play_count': sum(track.play_count for track in tracks),
    }
    return render(request, 'music/account.html', context)


@require_POST
def register_mock(request):
    if request.user.is_authenticated:
        return JsonResponse(account_payload(get_account_profile(request)))

    display_name = request.POST.get('display_name', '').strip()
    email = request.POST.get('email', '').strip() or 'example@gmail.com'
    username_seed = display_name or email.split('@')[0]
    username = unique_mock_username(username_seed)

    User = get_user_model()
    user = User.objects.create_user(username=username, email=email)
    user.set_unusable_password()
    user.save(update_fields=['password'])

    guest_profile = get_guest_profile_data(request)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.display_name = display_name or guest_profile.get('display_name', '')
    profile.plan = guest_profile.get('plan', profile.plan)
    profile.preferred_quality = guest_profile.get('preferred_quality', profile.preferred_quality)
    profile.notifications_enabled = guest_profile.get('notifications_enabled', profile.notifications_enabled)
    profile.library_auto_enhance = guest_profile.get('library_auto_enhance', profile.library_auto_enhance)
    profile.save()

    user.backend = f'{ModelBackend.__module__}.{ModelBackend.__qualname__}'
    login(request, user)
    clear_guest_profile(request)

    return JsonResponse(account_payload(get_account_profile(request)), status=201)

def karaoke(request, track_id):
    track = get_object_or_404(Track, id=track_id)
    return render(request, 'music/karaoke.html', {'track': track})

@require_POST
def toggle_like(request, track_id):
    track = get_object_or_404(Track, id=track_id)
    track.is_liked = not track.is_liked
    track.save()
    return JsonResponse({'is_liked': track.is_liked})

@require_POST
def record_play(request, track_id):
    track = get_object_or_404(Track, id=track_id)
    track.play_count += 1
    track.save()
    return JsonResponse({'play_count': track.play_count})

@require_http_methods(["DELETE"])
def delete_track(request, track_id):
    track = get_object_or_404(Track, id=track_id)

    # Delete files
    if track.audio_file:
        track.audio_file.delete(save=False)
    if track.processed_file:
        track.processed_file.delete(save=False)
    if track.cover_image:
        track.cover_image.delete(save=False)

    track.delete()
    return JsonResponse({'message': 'Track deleted'})

@require_http_methods(["PATCH"])
def edit_track(request, track_id):
    track = get_object_or_404(Track, id=track_id)
    try:
        data = json.loads(request.body)
        if 'title' in data:
            track.title = data['title']
        if 'artist' in data:
            track.artist = data['artist']
        track.save()
        return JsonResponse({'id': track.id, 'title': track.title, 'artist': track.artist})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def get_track_metrics(request, track_id):
    track = get_object_or_404(Track, id=track_id)
    if not track.processed_file:
        return JsonResponse({"error": "Track not processed"}, status=404)

    # Metrics are saved in debug_output/{filename}_metrics.json
    # processed_file.name is relative to MEDIA_ROOT, e.g. processed/track_ai.wav
    filename = os.path.basename(track.processed_file.name)
    base_name = os.path.splitext(filename)[0]

    # debug_output is in project root
    metrics_path = os.path.join(settings.BASE_DIR, 'debug_output', f"{base_name}_metrics.json")

    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, 'r') as f:
                data = json.load(f)
            return JsonResponse(data)
        except Exception as e:
            return JsonResponse({'error': f"Failed to read metrics: {str(e)}"}, status=500)
    else:
        return JsonResponse({'error': 'Metrics file not found'}, status=404)

def library_api(request):
    """API endpoint to get library tracks as JSON"""
    tracks = Track.objects.all().order_by('-created_at')
    data = []
    for t in tracks:
        data.append({
            'id': t.id,
            'title': t.title,
            'artist': t.artist,
            'status': t.status,
            'cover_path': t.cover_image.url if t.cover_image else None,
            'processed_path': t.processed_file.url if t.processed_file else None,
            'audio_url': t.audio_file.url if t.audio_file else None,
            'filename': os.path.basename(t.audio_file.name),
            'duration': t.duration,
            'is_liked': t.is_liked
        })
    return JsonResponse(data, safe=False)

def serve_processed_file(request, filename):
    # This view might be redundant if we serve via MEDIA_URL,
    # but for strict no-cache streaming it's useful.
    file_path = os.path.join(settings.MEDIA_ROOT, 'processed', filename)
    if not os.path.exists(file_path):
        return JsonResponse({'error': 'File not found'}, status=404)

    response = FileResponse(open(file_path, 'rb'))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response
