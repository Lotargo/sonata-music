from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload, name='upload'),
    path('process/<int:track_id>/', views.process_track, name='process_track'),
    path('library/', views.library_api, name='library_api'),
    path('cancel-upload/<int:track_id>/', views.cancel_pending_upload, name='cancel_pending_upload'),
    path('delete/<int:track_id>/', views.delete_track, name='delete_track'),
    path('edit/<int:track_id>/', views.edit_track, name='edit_track'),
    path('metrics/<int:track_id>/', views.get_track_metrics, name='get_track_metrics'),

    path('history/', views.history, name='history'),
    path('likes/', views.likes, name='likes'),
    path('account/', views.account, name='account'),
    path('register/mock/', views.register_mock, name='register_mock'),
    path('karaoke/<int:track_id>/', views.karaoke, name='karaoke'),
    path('api/like/<int:track_id>/', views.toggle_like, name='toggle_like'),
    path('api/dislike/<int:track_id>/', views.toggle_dislike, name='toggle_dislike'),
    path('api/play/<int:track_id>/', views.record_play, name='record_play'),
    path('api/openapi.json', views.openapi_spec, name='openapi_spec'),
    path('api/docs/', views.scalar_docs, name='scalar_docs'),
    path('health/', views.health_check, name='health_check'),
    path('api/health/', views.health_check, name='api_health_check'),
    path('favicon.ico', views.favicon_view, name='favicon'),

    # Custom file serving for processed files (no-cache)
    path('library_files/<path:filename>', views.serve_processed_file, name='serve_processed_file'),
]

# In development, serve media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
