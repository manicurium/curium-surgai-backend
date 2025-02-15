from django.urls import path
from .views import DeviceCreateView, get_device_details


urlpatterns = [
    path("device/register", DeviceCreateView.as_view(), name="device-register"),
    path("device", get_device_details, name="fetch-device"),
]
