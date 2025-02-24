from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .serializers import VideoSerializer, VideoUploadSerializer
import uuid
from django.core.exceptions import ValidationError
from .models import Video
from django.core.files.storage import default_storage
from django.conf import settings
import os
from rest_framework.parsers import MultiPartParser, FormParser


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
                "device-id",
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
            400: "Bad Request - Invalid or missing device-id",
            401: "Unauthorized",
        },
    )
    def get(self, request):
        device_id = request.headers.get("device-id")

        if not device_id:
            return Response(
                {"error": "device-id header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate UUID format
        valid_uuid = self.validate_uuid(device_id)
        if not valid_uuid:
            return Response(
                {"error": "Invalid device-id format. Must be a valid UUID."},
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


class VideoUploadView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        operation_description="Upload a new video file and start processing",
        request_body=VideoUploadSerializer,
        responses={
            201: openapi.Response(
                description="Video uploaded successfully", schema=VideoSerializer
            ),
            400: "Bad Request",
            401: "Unauthorized",
            413: "Request Entity Too Large",
            415: "Unsupported Media Type",
        },
    )
    def post(self, request):
        # Validate device ID
        device_id = request.headers.get("device-id")
        if not device_id:
            return Response(
                {"error": "device-id header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload_serializer = VideoUploadSerializer(data=request.data)
        if not upload_serializer.is_valid():
            return Response(
                upload_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get the uploaded file
            video_file = request.FILES["video_file"]

            # Validate file type
            allowed_types = [
                "video/mp4",
                "video/mpeg",
                "video/quicktime",
                "video/mov",
                "video/avi",
            ]
            if video_file.content_type not in allowed_types:
                return Response(
                    {"error": "Unsupported file type"},
                    status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )

            # Generate a unique filename
            file_extension = os.path.splitext(video_file.name)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"

            # Define the storage path
            relative_path = f"videos/{device_id}/{unique_filename}"
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)

            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Save the file
            with default_storage.open(relative_path, "wb+") as destination:
                for chunk in video_file.chunks():
                    destination.write(chunk)

            # Create video entry
            video_data = {
                "exercise_type": upload_serializer.validated_data["exercise_type"],
                "performer": str(request.user.id),
                "retain": upload_serializer.validated_data["retain"],
                "video_path": relative_path,
            }

            context = {"request": request}
            video_serializer = VideoSerializer(data=video_data, context=context)

            if video_serializer.is_valid():
                video = video_serializer.save()

                # Start background processing
                # process_video.delay(str(video.video_id), file_path)

                return Response(video_serializer.data, status=status.HTTP_201_CREATED)
            return Response(video_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Clean up file if saved
            if "relative_path" in locals():
                default_storage.delete(relative_path)

            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
