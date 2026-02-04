from django.db import models
import os

def track_upload_path(instance, filename):
    # Uploads go to MEDIA_ROOT/uploads/filename
    return os.path.join('uploads', filename)

def cover_upload_path(instance, filename):
    return os.path.join('covers', filename)

def processed_upload_path(instance, filename):
    return os.path.join('processed', filename)

class Track(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    title = models.CharField(max_length=255, blank=True, null=True)
    artist = models.CharField(max_length=255, blank=True, null=True, default='Unknown Artist')

    # Files
    audio_file = models.FileField(upload_to=track_upload_path)
    cover_image = models.ImageField(upload_to=cover_upload_path, blank=True, null=True)
    processed_file = models.FileField(upload_to=processed_upload_path, blank=True, null=True)

    # Metadata
    duration = models.FloatField(blank=True, null=True) # seconds
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    # User interactions
    is_liked = models.BooleanField(default=False)
    play_count = models.IntegerField(default=0)
    lyrics = models.TextField(blank=True, null=True)

    # Processing settings
    target_format = models.CharField(max_length=10, blank=True, null=True)
    target_bitrate = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.title or str(self.audio_file.name)
