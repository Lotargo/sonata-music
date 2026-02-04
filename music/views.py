from django.shortcuts import render, redirect
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
