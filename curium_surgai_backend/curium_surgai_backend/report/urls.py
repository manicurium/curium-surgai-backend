from django.urls import path
from .views import create_report, get_reports, get_report_detail
from rest_framework_simplejwt import views as jwt_views

urlpatterns = [
    path("api/reports/create/", create_report, name="create_report"),  # Create a new report
    path("api/reports/", get_reports, name="get_reports"),  # List all reports
    path("api/reports/<uuid:report_id>/", get_report_detail, name="get_report_detail"),  # Get report details by report_id

    path("auth/token", jwt_views.TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh", jwt_views.TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/revoke", jwt_views.TokenBlacklistView.as_view(), name="auth_logout"),
]
