from django.urls import path
from .views import create_license, get_licenses, get_license_detail

urlpatterns = [
    path("licenses/create", create_license, name="create_license"),
    path("licenses", get_licenses, name="get_licenses"),
    path("licenses/<uuid:license_id>", get_license_detail, name="get_license_detail"),
]
