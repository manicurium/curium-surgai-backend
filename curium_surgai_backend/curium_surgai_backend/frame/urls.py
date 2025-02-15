from django.urls import path

from .views import ProcessedFrameCreateView, CollateFramesView

urlpatterns = [
    path("frame", ProcessedFrameCreateView.as_view(), name="frame-create"),
    path("frame/collate", CollateFramesView.as_view(), name="frame-collate"),
]
