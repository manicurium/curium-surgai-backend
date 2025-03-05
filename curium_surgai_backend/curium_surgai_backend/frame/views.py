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
import cv2
from video.serializers import VideoSerializer
from report.serializers import ReportSerializer
from drf_yasg import openapi
import threading
from django.db import transaction
from django.core.cache import cache
import logging
from utils import S3Utils
import piexif
from datetime import datetime
from paho.mqtt import client as mqtt_client
import ssl

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
        json_dir = os.path.join(
            settings.MEDIA_ROOT, str(device_id), str(session_id), "json"
        )
        os.makedirs(frame_dir, exist_ok=True)
        os.makedirs(json_dir, exist_ok=True)

        # Open image and extract EXIF metadata
        image = Image.open(frame_file)
        json_data = None
        try:
            exif_dict = piexif.load(image.info.get("exif", b""))
            logger.info(f"Extracted EXIF Data: {exif_dict}")
            user_comment = exif_dict["Exif"].get(piexif.ExifIFD.UserComment)
            if user_comment:
                try:
                    json_data = json.loads(user_comment.decode("utf-8"))
                except UnicodeDecodeError:
                    json_data = json.loads(user_comment.decode("utf-16"))
        except (KeyError, ValueError, json.JSONDecodeError):
            pass

        if not json_data:
            raise ValueError("No valid EXIF metadata found in image.")

        # Extract frame number
        frame_number = json_data.get("frame_number")
        if frame_number is None:
            raise ValueError("Frame number missing in metadata.")

        # Save frame image
        frame_filename = f"frame_{frame_number}.jpg"
        frame_path = os.path.join(frame_dir, frame_filename)
        image.save(frame_path, "JPEG", exif=image.info.get("exif"))

        # Save JSON metadata
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

        # Initialize MQTT client for publishing results
        self.mqtt_client = None
        try:
            # Configuration for MQTT
            mqtt_broker = settings.MQTT_BROKER
            mqtt_port = settings.MQTT_PORT
            mqtt_username = settings.MQTT_USERNAME
            mqtt_password = settings.MQTT_PASSWORD
            cert_path = settings.CERTIFICATE_PATH

            # Create MQTT client
            self.mqtt_client = mqtt_client.Client()

            # Setup TLS if certificate path exists
            if os.path.exists(cert_path):
                try:
                    # Setup TLS with certificates
                    self.mqtt_client.tls_set(
                        ca_certs=f"{cert_path}/ca.crt",
                        certfile=f"{cert_path}/device/client.crt",
                        keyfile=f"{cert_path}/device/client.key",
                        cert_reqs=ssl.CERT_REQUIRED,
                        tls_version=ssl.PROTOCOL_TLSv1_2,
                    )
                    self.mqtt_client.tls_insecure_set(True)
                    self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
                    logger.info(
                        f"TLS configured for MQTT client with certificates from {cert_path}"
                    )
                except Exception as e:
                    logger.error(f"Failed to setup TLS for MQTT client: {e}")
                    # Fall back to username/password only if TLS setup fails
                    if mqtt_username and mqtt_password:
                        self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)
            elif mqtt_username and mqtt_password:
                # Use username/password if no certificates
                self.mqtt_client.username_pw_set(mqtt_username, mqtt_password)

            # Connect to broker
            self.mqtt_client.connect(mqtt_broker, mqtt_port)
            self.mqtt_client.loop_start()
            logger.info(f"MQTT client initialized and connected for device {device_id}")
        except Exception as e:
            logger.error(f"Failed to initialize MQTT client: {e}")
            self.mqtt_client = None

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

            video = None
            report = None

            with transaction.atomic():
                # Create serializer with context
                serializer = VideoSerializer(
                    data=self.video_data, context={"request": self.request}
                )

                if not serializer.is_valid():
                    raise Exception(f"Invalid video data: {serializer.errors}")

                # Clean up frame files
                video = serializer.save()

                # Create report
                report = self.create_report(report_json=master_json, video=video)

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

            # Publish results to MQTT
            if video and report and self.mqtt_client:
                self.publish_results(video, report)

            cache.set(self.status_key, "completed", timeout=3600)

        except Exception as e:
            logger.error(f"Video processing failed: {str(e)}")
            cache.set(self.status_key, f"failed: {str(e)}", timeout=3600)
        finally:
            # Clean up MQTT client
            if self.mqtt_client:
                try:
                    self.mqtt_client.loop_stop()
                    self.mqtt_client.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting MQTT client: {e}")

    def publish_results(self, video, report):
        """Publish processing results to MQTT topic"""
        try:
            # Prepare result data
            result_data = {
                "video_id": str(video.video_id),
                "result_date": datetime.now().isoformat(),
                "score": report.score.get("score", ""),
                "comments": "Video processing completed successfully",
            }

            # Set topic
            topic = f"video/result/{self.device_id}"

            # Publish to MQTT
            result = self.mqtt_client.publish(
                topic, json.dumps(result_data)  # At least once delivery
            )

            # Check if publishing was successful
            if result.rc == mqtt_client.MQTT_ERR_SUCCESS:
                logger.info(f"Published results to {topic} successfully")
            else:
                logger.error(f"Failed to publish results to {topic}: {result.rc}")

        except Exception as e:
            logger.exception(f"Error publishing results to MQTT: {e}")

    def create_report(self, report_json, video):
        score = {"score": 4.5}
        data = {"report_json": report_json, "video": video.video_id, "score": score}
        serializer = ReportSerializer(data=data)
        if not serializer.is_valid():
            raise Exception(f"Invalid video data: {serializer.errors}")
        else:
            logger.info("create report entry")
            report = serializer.save()
            return report

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
            if "output_path" in locals() and os.path.exists(output_path):
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
