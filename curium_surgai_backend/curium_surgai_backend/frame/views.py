from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_yasg.utils import swagger_auto_schema
from django.db import transaction
from .serializers import ProcessedFrameSerializer
from django.conf import settings
import json
import os
import uuid
from PIL import Image
from PIL.ExifTags import TAGS
import cv2
from video.serializers import VideoSerializer
from report.serializers import ReportSerializer
from drf_yasg import openapi
import threading
from django.db import transaction
from django.core.cache import cache
import logging
from utils import S3Utils


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

INVALID_HEADER = "Invalid device-id format. Must be a valid UUID."
s3util = S3Utils(
    bucket_name=os.getenv("BUCKET_NAME"),
    access_key=os.getenv("AWS_ACCESS_KEY_ID"),
    secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region=os.getenv("AWS_REGION"),
)


class ProcessedFrameCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def validate_uuid(self, uuid_string):
        try:
            uuid_obj = uuid.UUID(uuid_string)
            return str(uuid_obj)
        except ValueError:
            return None

    def save_frame_files(self, frame_file, device_id, session_id):
        # Create directory structure
        frame_dir = os.path.join(
            settings.MEDIA_ROOT, str(device_id), str(session_id), "frames"
        )
        os.makedirs(frame_dir, exist_ok=True)

        image = Image.open(frame_file)
        exif = image._getexif()
        json_data = None
        for tag_id in exif:
            tag = TAGS.get(tag_id, tag_id)
            if tag == "UserComment":
                json_data = json.loads(exif[tag_id])
                break
        json_dir = os.path.join(
            settings.MEDIA_ROOT, str(device_id), str(session_id), "json"
        )
        frame_number = json_data.get("frame_number")
        # Save frame image
        frame_filename = f"frame_{frame_number}.jpg"
        frame_path = os.path.join(frame_dir, frame_filename)
        with open(frame_path, "wb+") as destination:
            for chunk in frame_file.chunks():
                destination.write(chunk)

        # Extract and save JSON
        # image = Image.open(frame_file)
        # exif = image._getexif()
        # json_data = None
        # for tag_id in exif:
        #     tag = TAGS.get(tag_id, tag_id)
        #     if tag == "UserComment":
        #         json_data = json.loads(exif[tag_id])
        #         break
        # json_dir = os.path.join(
        #     settings.MEDIA_ROOT, str(device_id), str(session_id), "json"
        # )
        os.makedirs(json_dir, exist_ok=True)
        json_filename = f"frame_{frame_number}.json"
        json_path = os.path.join(json_dir, json_filename)
        with open(json_path, "w") as json_file:
            json.dump(json_data, json_file)

        return frame_path, json_path

    @swagger_auto_schema(
        operation_description="Upload a processed frame with EXIF data",
        manual_parameters=[
            openapi.Parameter(
                "device-id",
                openapi.IN_HEADER,
                description="Unique identifier for the device (must be a valid UUID)",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=True,
            ),
            openapi.Parameter(
                "session-id",
                openapi.IN_HEADER,
                description="Unique identifier for the session (can be timestamp)",
                type=openapi.TYPE_STRING,
                format="int",
                required=True,
            ),
        ],
        request_body=ProcessedFrameSerializer,
        responses={
            201: ProcessedFrameSerializer,
            400: "Bad Request",
            401: "Unauthorized",
        },
    )
    def post(self, request):
        device_id = request.headers.get("device-id")
        session_id = request.headers.get("session-id")
        if not device_id:
            return Response(
                {"error": "device-id header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_uuid = self.validate_uuid(device_id)
        if not valid_uuid:
            return Response(
                {"error": INVALID_HEADER},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Add device_id to the data
        request.data["device_id"] = valid_uuid

        # serializer = ProcessedFrameSerializer(data=request.data)

        # if serializer.is_valid():
        #     frame_file = serializer.validated_data.pop("frame_file")
        try:
            # frame_number = serializer.validated_data["frame_number"]

            # Save files and get paths
            _, _ = self.save_frame_files(
                request.data["frame_file"], valid_uuid, session_id
            )

            return Response(
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            logger.exception(e)
            return Response(
                "failed to upload frame", status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VideoProcessingThread(threading.Thread):
    def __init__(self, device_id, session_id, request, video_data):
        threading.Thread.__init__(self)
        self.device_id = device_id
        self.session_id = session_id
        self.request = request
        self.video_data = video_data
        self.status_key = f"video_processing_{device_id}"

    def run(self):
        try:
            cache.set(self.status_key, "processing", timeout=3600)  # 1 hour timeout

            # Collate JSON files
            master_json = []

            json_path = os.path.join(
                settings.MEDIA_ROOT, str(self.device_id), str(self.session_id), "json"
            )
            jsons = sorted([f for f in os.listdir(json_path) if f.endswith(".json")])

            for frame in jsons:
                with open(os.path.join(json_path, frame), "r") as json_file:
                    frame_data = json.load(json_file)
                    master_json.append(frame_data)
            master_json = sorted(master_json, key=lambda x: x["frame_number"])
            os.makedirs(
                os.path.join(
                    settings.MEDIA_ROOT,
                    str(self.device_id),
                    str(self.session_id),
                    "video",
                ),
                exist_ok=True,
            )
            json_path = os.path.join(
                settings.MEDIA_ROOT,
                str(self.device_id),
                str(self.session_id),
                "video",
                "master.json",
            )
            with open(json_path, "w") as json_file:
                json.dump(master_json, json_file)

            # Create video from frames
            video_path = self._create_video_from_frames()
            if not video_path:
                raise Exception("Failed to create video file")

            video_url = self.upload_to_s3(video_path=video_path)
            logger.info(f"video path: {video_url}")

            # Prepare video data
            self.video_data["video_path"] = video_url

            logger.info(f"create video entry {self.video_data}")
            with transaction.atomic():
                # Create serializer with context
                serializer = VideoSerializer(
                    data=self.video_data, context={"request": self.request}
                )

                if not serializer.is_valid():
                    raise Exception(f"Invalid video data: {serializer.errors}")

                # Clean up frame files

                video = serializer.save()

                self.create_report(report_json=master_json, video=video)
                frames_path = os.path.join(
                    settings.MEDIA_ROOT,
                    str(self.device_id),
                    str(self.session_id),
                    "frames",
                )
                for frame_file in os.listdir(frames_path):
                    frame_path = os.path.join(frames_path, frame_file)
                    if not frame_path.endswith(".avi"):
                        os.remove(frame_path)

                # Save video and delete frames
                json_path = os.path.join(
                    settings.MEDIA_ROOT,
                    str(self.device_id),
                    str(self.session_id),
                    "json",
                )

                for json_file in os.listdir(json_path):
                    frame_path = os.path.join(json_path, json_file)
                    if not frame_path.startswith("master"):
                        os.remove(frame_path)

            cache.set(self.status_key, "completed", timeout=3600)

        except Exception as e:
            logger.error(f"Video processing failed: {str(e)}")
            cache.set(self.status_key, f"failed: {str(e)}", timeout=3600)

    def create_report(self, report_json, video):
        score = {"score": 4.5}
        data = {"report_json": report_json, "video": video.video_id, "score": score}
        serializer = ReportSerializer(data=data)
        if not serializer.is_valid():
            raise Exception(f"Invalid video data: {serializer.errors}")
        else:
            logger.info("create report entry")
            serializer.save()

    def upload_to_s3(self, video_path):
        s3util.upload_file(file_location=video_path, key=video_path.replace("\\", "/"))

        url = s3util.generate_presigned_url(
            object_key=video_path.replace("\\", "/"),
            expiry=os.getenv("S3_SIGNED_URL_EXPIRY", 604800),
        )
        logger.info(f"Video created at {video_path}")
        return url

    def sort_frame_files_simple(self, directory):
        # Get all jpg files in the directory
        frame_files = [
            f
            for f in os.listdir(directory)
            if f.startswith("frame_") and f.endswith(".jpg")
        ]

        # Sort files based on the number in the filename
        def get_frame_number(filename):
            # Remove 'frame_' and '.jpg' and convert to integer
            return int(filename[6:-4])

        sorted_frames = sorted(frame_files, key=get_frame_number)
        return sorted_frames

    def _create_video_from_frames(self):
        try:
            folder_path = os.path.join(
                settings.MEDIA_ROOT, str(self.device_id), str(self.session_id), "frames"
            )
            frames = self.sort_frame_files_simple(folder_path)
            if not frames:
                return

            # Read first frame for dimensions
            first_frame = cv2.imread(os.path.join(folder_path, frames[0]))
            height, width = first_frame.shape[:2]

            # Create video
            output_path = os.path.join(
                settings.MEDIA_ROOT,
                str(self.device_id),
                str(self.session_id),
                "video",
                "outcome.avi",
            )
            fourcc = cv2.VideoWriter_fourcc("F", "M", "P", "4")
            out = cv2.VideoWriter(output_path, fourcc, 30.0, (width, height))

            # Add frames to video
            for frame_file in frames:
                frame_path = os.path.join(folder_path, frame_file)
                frame = cv2.imread(frame_path)
                out.write(frame)

            out.release()
            return output_path
        except Exception as e:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise e


class CollateFramesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def validate_uuid(self, uuid_string):
        try:
            uuid_obj = uuid.UUID(uuid_string)
            return str(uuid_obj)
        except ValueError:
            return None

    @swagger_auto_schema(
        operation_description="Collate frames into video and create master JSON",
        manual_parameters=[
            openapi.Parameter(
                "device-id",
                openapi.IN_HEADER,
                description="Unique identifier for the device (must be a valid UUID)",
                type=openapi.TYPE_STRING,
                format="uuid",
                required=True,
            ),
            openapi.Parameter(
                "session-id",
                openapi.IN_HEADER,
                description="Unique identifier for the session (can be timestamp)",
                type=openapi.TYPE_STRING,
                format="int",
                required=True,
            ),
        ],
        request_body=VideoSerializer,
        responses={
            202: "Processing started",
            400: "Bad Request",
            401: "Unauthorized",
            404: "Frames not found",
        },
    )
    def post(self, request):
        device_id = request.headers.get("device-id")
        session_id = request.headers.get("session-id")
        if not device_id or not session_id:
            return Response(
                {"error": INVALID_HEADER},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_uuid = self.validate_uuid(device_id)
        if not valid_uuid:
            return Response(
                {"error": INVALID_HEADER},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if a processing task is already running for this device
        status_key = f"video_processing_{valid_uuid}"
        current_status = cache.get(status_key)
        if current_status and current_status == "processing":
            return Response(
                {"error": "Video processing is already in progress for this device"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Start processing thread
        context = {"request": request}
        video_data = {
            "exercise_type": request.data.get("exercise_type"),
            "performer": str(context["request"].user.id),
            "retain": request.data.get("retain", False),
        }
        logger.info(video_data)
        processing_thread = VideoProcessingThread(
            valid_uuid, session_id, request, video_data
        )
        processing_thread.start()

        return Response(
            {"message": "Video processing started", "status_key": status_key},
            status=status.HTTP_202_ACCEPTED,
        )

    def get(self, request):
        """Check the status of video processing"""
        device_id = request.headers.get("device-id")
        if not device_id:
            return Response(
                {"error": "device-id header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_uuid = self.validate_uuid(device_id)
        if not valid_uuid:
            return Response(
                {"error": "Invalid device-id format. Must be a valid UUID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        status_key = f"video_processing_{valid_uuid}"
        current_status = cache.get(status_key)

        return Response({"status": current_status or "not_found"})
