from django.urls import path
from .views import VideoCreateView

urlpatterns = [
    path("video", VideoCreateView.as_view(), name="upload_video"),
    # path("videos", get_videos, name="get_videos"),
    # path("videos/<uuid:video_id>", get_video_detail, name="get_video_detail"),
]
