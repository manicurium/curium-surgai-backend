from django.urls import path
from .views import upload_video, get_videos, get_video_detail

urlpatterns = [
    # Video APIs
    path("api/videos/upload/", upload_video, name="upload_video"),  # Upload video
    path("api/videos/", get_videos, name="get_videos"),  # List videos for the authenticated user
    path("api/videos/<uuid:video_id>/", get_video_detail, name="get_video_detail"),  # Get video details by video_id
]
