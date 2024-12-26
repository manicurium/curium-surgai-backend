from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from .models import Report
from .serializers import ReportSerializer

# Report creation view - user can create a new report
@swagger_auto_schema(
    method="post",
    request_body=ReportSerializer,
    responses={201: ReportSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can create reports
def create_report(request):
    if request.method == "POST":
        serializer = ReportSerializer(data=request.data)

        # Ensure the data is valid
        if serializer.is_valid():
            serializer.save()  # Save the report
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Report list view - user can get a list of all reports
@swagger_auto_schema(
    method="get",
    responses={200: ReportSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can view reports
def get_reports(request):
    reports = Report.objects.all()  # Retrieve all reports

    # Serialize the reports and return them
    serializer = ReportSerializer(reports, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

# Report detail view - user can get details for a specific report by report_id
@swagger_auto_schema(
    method="get",
    responses={200: ReportSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_report_detail(request, report_id):
    try:
        report = Report.objects.get(report_id=report_id)  # Retrieve report by UUID
    except Report.DoesNotExist:
        return Response({"detail": "Report not found."}, status=status.HTTP_404_NOT_FOUND)

    # Serialize and return the report details
    serializer = ReportSerializer(report)
    return Response(serializer.data, status=status.HTTP_200_OK)
