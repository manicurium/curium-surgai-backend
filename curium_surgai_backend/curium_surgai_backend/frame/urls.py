from django.urls import path

from .views import ProcessedFrameCreateView

urlpatterns = [
    path("frame/", ProcessedFrameCreateView.as_view(), name="frame-create")
    # path("frames", get_frames, name="get_frames"),
    # path("frames/<uuid:processed_frame_id>", get_frame_detail, name="get_frame_detail"),
]
