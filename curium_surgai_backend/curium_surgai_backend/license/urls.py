from django.urls import path
from .views import create_license, get_licenses, get_license_detail
from rest_framework_simplejwt import views as jwt_views

urlpatterns = [
    path("api/licenses/create/", create_license, name="create_license"),  # Create a new license
    path("api/licenses/", get_licenses, name="get_licenses"),  # List all licenses
    path("api/licenses/<uuid:license_id>/", get_license_detail, name="get_license_detail"),  # Get license details by license_id

    path("auth/token", jwt_views.TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh", jwt_views.TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/revoke", jwt_views.TokenBlacklistView.as_view(), name="auth_logout"),
]
