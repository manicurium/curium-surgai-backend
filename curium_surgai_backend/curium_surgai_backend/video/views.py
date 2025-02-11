from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .serializers import VideoSerializer
import uuid
from django.core.exceptions import ValidationError
from .models import Video


class VideoCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new video entry",
        request_body=VideoSerializer,
        responses={
            201: openapi.Response(
                description="Video created successfully", schema=VideoSerializer
            ),
            400: "Bad Request",
            401: "Unauthorized",
        },
    )
    def post(self, request):
        context = {"request": request}
        serializer = VideoSerializer(data=request.data, context=context)

        if serializer.is_valid():

            # Automatically set the uploaded_by field to current user
            _ = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def validate_uuid(self, uuid_string):
        try:
            uuid_obj = uuid.UUID(uuid_string)
            return str(uuid_obj)
        except (ValueError, AttributeError, TypeError):
            return None

    @swagger_auto_schema(
        operation_description="Get all videos uploaded by a specific device",
        manual_parameters=[
            openapi.Parameter(
                "Device-ID",
                openapi.IN_HEADER,
                description="Unique identifier for the device (must be a valid UUID)",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=True,
            )
        ],
        responses={
            200: openapi.Response(
                description="List of videos retrieved successfully",
                schema=VideoSerializer(many=True),
            ),
            400: "Bad Request - Invalid or missing Device-ID",
            401: "Unauthorized",
        },
    )
    def get(self, request):
        device_id = request.headers.get("Device-ID")

        if not device_id:
            return Response(
                {"error": "Device-ID header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate UUID format
        valid_uuid = self.validate_uuid(device_id)
        if not valid_uuid:
            return Response(
                {"error": "Invalid Device-ID format. Must be a valid UUID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            videos = Video.objects.filter(uploaded_by=valid_uuid)
            serializer = VideoSerializer(videos, many=True)
            return Response(serializer.data)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "An error occurred while retrieving videos"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
