from django.urls import path
from .views import upload_frame, get_frames, get_frame_detail

urlpatterns = [
    path("frames/upload", upload_frame, name="upload_frame"),
    path("frames", get_frames, name="get_frames"),
    path("frames/<uuid:processed_frame_id>", get_frame_detail, name="get_frame_detail"),
]
