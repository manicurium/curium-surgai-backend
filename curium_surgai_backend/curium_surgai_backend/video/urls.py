from django.urls import path
from .views import VideoCreateView, VideoUploadView

urlpatterns = [
    path("video", VideoCreateView.as_view(), name="video"),
    path("video/upload", VideoUploadView.as_view(), name="video"),
    # path("videos", get_videos, name="get_videos"),
    # path("videos/<uuid:video_id>", get_video_detail, name="get_video_detail"),
]
