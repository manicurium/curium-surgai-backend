from django.urls import path
from .views import DeviceCreateView, start_stream, get_device_details


urlpatterns = [
    path("device/register", DeviceCreateView.as_view(), name="device-register"),
    path("stream/start", start_stream, name="start-stream"),
    path("device", get_device_details, name="fetch-device"),
]
