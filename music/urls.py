from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload, name='upload'),
    path('history/', views.history, name='history'),
    path('likes/', views.likes, name='likes'),
    path('account/', views.account, name='account'),
    path('karaoke/<int:track_id>/', views.karaoke, name='karaoke'),
    path('api/like/<int:track_id>/', views.toggle_like, name='toggle_like'),
    path('api/play/<int:track_id>/', views.record_play, name='record_play'),
]
