from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .models import Video, Report
from .serializers import ReportSerializer


class ReportCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a report for a video",
        request_body=ReportSerializer,
        responses={
            201: ReportSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            404: "Video not found",
        },
    )
    def post(self, request):
        # Add video validation to ensure user owns the video
        video_id = request.data.get("video")
        if video_id:
            video = get_object_or_404(Video, video_id=video_id)
            if str(video.performer) != str(request.user.id):
                return Response(
                    {
                        "error": "You don't have permission to create reports for this video"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = ReportSerializer(data=request.data)
        if serializer.is_valid():
            report = serializer.save()
            return Response(
                ReportSerializer(report).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Get reports for a specific video",
        manual_parameters=[
            openapi.Parameter(
                "video_id",
                openapi.IN_QUERY,
                description="ID of the video to get reports for",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ],
        responses={
            200: ReportSerializer(many=True),
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Video not found",
        },
    )
    def get(self, request):
        video_id = request.query_params.get("video_id")
        if not video_id:
            return Response(
                {"error": "video_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the video and check permissions
        video = get_object_or_404(Video, video_id=video_id)

        if str(video.performer) != str(request.user.id):
            return Response(
                {"error": "You don't have permission to view reports for this video"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get all reports for the video
        reports = Report.objects.filter(video=video)
        serializer = ReportSerializer(reports, many=True)

        return Response(serializer.data)
