from django.urls import path
from .views import create_report, get_reports, get_report_detail

urlpatterns = [
    path("reports/create", create_report, name="create_report"),
    path("reports", get_reports, name="get_reports"),
    path("reports/<uuid:report_id>", get_report_detail, name="get_report_detail"),
]
