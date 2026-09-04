from django.contrib import admin
from django.urls import path, include, re_path
from music.views import ranged_media_serve

urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(r"^media/(?P<path>.*)$", ranged_media_serve, name="ranged_media_serve"),
    path("", include("music.urls")),
]
