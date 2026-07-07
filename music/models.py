from django.conf import settings
from django.db import models
import os

AUDIO_EXTENSIONS = ('.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.aiff', '.aif')


def track_upload_path(instance, filename):
    # Uploads go to MEDIA_ROOT/uploads/filename
    return os.path.join('uploads', filename)


def cover_upload_path(instance, filename):
    return os.path.join('covers', filename)


def processed_upload_path(instance, filename):
    return os.path.join('processed', filename)


def avatar_upload_path(instance, filename):
    return os.path.join('avatars', f'user_{instance.user_id}', filename)


class UserProfile(models.Model):
    PLAN_CHOICES = [
        ('standard', 'Standard'),
        ('pro', 'Pro'),
    ]

    QUALITY_CHOICES = [
        ('balanced', 'Balanced / 256 kbps'),
        ('high', 'High / 320 kbps'),
        ('lossless', 'Lossless / WAV'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=80, blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='standard')
    preferred_quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, default='high')
    notifications_enabled = models.BooleanField(default=True)
    library_auto_enhance = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_pro(self):
        return self.plan == 'pro'

    @property
    def public_name(self):
        return self.display_name or self.user.get_username()

    def __str__(self):
        return f'{self.user} profile'


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

    @property
    def original_filename(self):
        return os.path.basename(self.audio_file.name) if self.audio_file else ''

    @property
    def processed_filename(self):
        return os.path.basename(self.processed_file.name) if self.processed_file else ''

    @property
    def display_title(self):
        raw_title = (self.title or '').strip()
        original_name = self.original_filename
        title_looks_like_source_file = (
            not raw_title
            or raw_title == original_name
            or raw_title.lower().endswith(AUDIO_EXTENSIONS)
        )

        if self.status == 'completed' and self.processed_filename and title_looks_like_source_file:
            return self.processed_filename
        return raw_title or original_name or 'Без названия'

    @property
    def display_format(self):
        name = self.processed_filename if self.status == 'completed' and self.processed_filename else self.original_filename
        ext = os.path.splitext(name)[1].lstrip('.')
        return ext.upper() if ext else (self.target_format or '').upper()

    def __str__(self):
        return self.display_title
