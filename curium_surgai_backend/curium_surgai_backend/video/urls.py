from django.urls import path
from .views import upload_video, get_videos, get_video_detail

urlpatterns = [
    path("videos/upload", upload_video, name="upload_video"),
    path("videos", get_videos, name="get_videos"),
    path("videos/<uuid:video_id>", get_video_detail, name="get_video_detail"),
]
