from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Track

def index(request):
    tracks = Track.objects.all().order_by('-created_at')
    return render(request, 'music/index.html', {'tracks': tracks})

def upload(request):
    if request.method == 'POST' and request.FILES.get('audio_file'):
        audio_file = request.FILES['audio_file']
        cover_image = request.FILES.get('cover_image')
        title = request.POST.get('title')
        artist = request.POST.get('artist')

        track = Track(
            title=title if title else audio_file.name,
            artist=artist if artist else 'Unknown Artist',
            audio_file=audio_file,
            cover_image=cover_image,
            status='pending'
        )
        track.save()
        return redirect('index')

    return render(request, 'music/upload.html')

def history(request):
    # Sort by play_count for "Most Played" or recently updated for now
    # Since we don't have a separate History model, we use play_count
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
