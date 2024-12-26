from django.urls import path
from .views import upload_frame, get_frames, get_frame_detail

urlpatterns = [
    path("api/frames/upload/", upload_frame, name="upload_frame"),  # Upload frame
    path("api/frames/", get_frames, name="get_frames"),  # List frames for the authenticated user
    path("api/frames/<uuid:processed_frame_id>/", get_frame_detail, name="get_frame_detail"),  # Get frame details by processed_frame_id
]
