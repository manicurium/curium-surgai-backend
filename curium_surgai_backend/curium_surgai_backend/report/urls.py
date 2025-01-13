from django.urls import path
from .views import ReportCreateView

urlpatterns = [
    path("reports/", ReportCreateView.as_view(), name="create_report"),
    # path("reports", get_reports, name="get_reports"),
    # path("reports/<uuid:report_id>", get_report_detail, name="get_report_detail"),
]
