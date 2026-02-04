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

from .models import Track
from .services.upscaler import upscaler
from .services.metadata import extract_metadata

logger = logging.getLogger(__name__)

def index(request):
    tracks = Track.objects.all().order_by('-created_at')
    return render(request, 'music/index.html', {'tracks': tracks})

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
        track.save()

        # Call Service
        success = upscaler.process_track(
            input_path=input_path,
            output_path=output_path,
            mode=mode,
            ddim_steps=int(params.get('steps', 50)),
            guidance_scale=float(params.get('guidance', 3.5)),
            seed=int(params.get('seed', 42)),
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

    # Extract DSP params separately
    dsp_params = {
        "reverb_enabled": data.get("reverb_enabled"),
        "reverb_size": float(data.get("reverb_size")) if data.get("reverb_size") is not None else None,
        "reverb_amount": float(data.get("reverb_amount")) if data.get("reverb_amount") is not None else None,
        "bass_boost": float(data.get("bass_boost")) if data.get("bass_boost") is not None else None,
        "voice_clarity": float(data.get("voice_clarity")) if data.get("voice_clarity") is not None else None,
        "compressor_amount": float(data.get("compressor_amount")) if data.get("compressor_amount") is not None else None,
        "stereo_width": float(data.get("stereo_width")) if data.get("stereo_width") is not None else None,
    }

    # Update track info if provided
    if 'title' in data:
        track.title = data['title']
    if 'artist' in data:
        track.artist = data['artist']
    track.save()

    params = {
        'mode': data.get('mode', 'ai'),
        'format': data.get('format', 'wav'),
        'sample_rate': data.get('sample_rate', 48000),
        'bitrate': data.get('bitrate', '320k'),
        'steps': data.get('steps', 50),
        'guidance': data.get('guidance', 3.5),
        'seed': data.get('seed', 42),
        'dsp_preset': data.get('dsp_preset', 'mastering'),
        'dsp_params': dsp_params
    }

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

def account(request):
    return render(request, 'music/account.html')

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
