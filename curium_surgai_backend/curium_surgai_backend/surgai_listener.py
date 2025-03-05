import cv2
import numpy as np
import os
import threading
import time
import logging
from paho.mqtt import client as mqtt_client
import ssl
from collections import defaultdict
import json
import requests
from utils import S3Utils
import zlib
import piexif
import io
from PIL import Image
import base64

logger = logging.getLogger(__name__)

s3util = S3Utils(
    bucket_name=os.getenv("BUCKET_NAME"),
    access_key=os.getenv("AWS_ACCESS_KEY_ID"),
    secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region=os.getenv("AWS_REGION"),
)


class VideoStreamHandler:
    def __init__(self, base_output_folder, stream_timeout=60):
        self.base_output_folder = base_output_folder
        self.stream_timeout = stream_timeout
        self.frames_buffer = defaultdict(dict)  # {device_id: {timestamp: frame_count}}
        self.last_frame_times = {}  # {(device_id, timestamp): last_frame_time}
        self.lock = threading.Lock()
        self.running = True

        os.makedirs(base_output_folder, exist_ok=True)
        # self.monitor_thread = threading.Thread(target=self._monitor_streams)
        # self.monitor_thread.start()

    def handle_frame(self, device_id, timestamp, frame_data):
        try:
            with self.lock:
                if timestamp not in self.frames_buffer[device_id]:
                    self.frames_buffer[device_id][timestamp] = 0

                frame_count = self.frames_buffer[device_id][timestamp]

                # Create output directory
                device_folder = os.path.join(
                    self.base_output_folder, device_id, timestamp
                )
                os.makedirs(os.path.join(device_folder, "json"), exist_ok=True)

                # Base filename without extension
                base_filename = f"frame_{frame_count:06d}"
                image = Image.open(io.BytesIO(frame_data))

                # Extract EXIF metadata
                try:
                    exif_dict = piexif.load(frame_data)
                    metadata_bytes = exif_dict["Exif"][piexif.ExifIFD.UserComment]
                    metadata = json.loads(metadata_bytes.decode("utf-8"))

                    # Save metadata to JSON file
                    with open(
                        os.path.join(device_folder, "json", f"{base_filename}.json"),
                        "w",
                    ) as f:
                        json.dump(metadata, f, indent=4)
                except Exception as e:
                    logger.exception(e)

                os.makedirs(os.path.join(device_folder, "frames"), exist_ok=True)
                image.save(
                    os.path.join(device_folder, "frames", f"{base_filename}.jpg"),
                    "JPEG",
                    exif=image.info["exif"],
                )

                self.frames_buffer[device_id][timestamp] += 1
                self.last_frame_times[(device_id, timestamp)] = time.time()
        except Image.UnidentifiedImageError as ex:
            logger.info(f"Frame data length: {len(frame_data)}")
            logger.info(f"First few bytes: {frame_data[:20]}")
            logger.error(ex)
        except Exception as e:
            logger.exception(f"Error handling frame: {e}")

    def handle_frame_base64(
        self, device_id, timestamp, frame_data_base64, frame_number=None
    ):
        try:
            with self.lock:
                if timestamp not in self.frames_buffer[device_id]:
                    self.frames_buffer[device_id][timestamp] = 0

                # Decode base64 data
                try:
                    # If it's already binary data, don't try to decode it
                    if isinstance(frame_data_base64, bytes):
                        frame_data = frame_data_base64
                    else:
                        # Ensure proper padding for base64
                        if isinstance(frame_data_base64, str):
                            # Add padding if necessary
                            padding_needed = len(frame_data_base64) % 4
                            if padding_needed > 0:
                                frame_data_base64 += "=" * (4 - padding_needed)

                        frame_data = base64.b64decode(frame_data_base64)
                except Exception as e:
                    logger.error(f"Failed to decode base64 data: {e}")
                    logger.error(
                        f"Data type: {type(frame_data_base64)}, First 20 chars: {str(frame_data_base64)[:20]}"
                    )
                    return

                # Use provided frame_number if given, otherwise use counter
                if frame_number is not None:
                    # Convert to integer if it's a string
                    if isinstance(frame_number, str):
                        try:
                            frame_number = int(frame_number)
                        except ValueError:
                            logger.error(f"Invalid frame number format: {frame_number}")
                            frame_number = self.frames_buffer[device_id][timestamp]
                else:
                    frame_number = self.frames_buffer[device_id][timestamp]

                # Create output directory
                device_folder = os.path.join(
                    self.base_output_folder, device_id, timestamp
                )
                os.makedirs(os.path.join(device_folder, "json"), exist_ok=True)

                # Base filename using the frame number
                base_filename = f"frame_{frame_number:06d}"

                try:
                    # Look for JPEG signature in the data
                    jpeg_signature = b"\xff\xd8\xff"
                    signature_pos = frame_data.find(jpeg_signature)

                    if signature_pos > 0:
                        # Found signature not at the beginning, extract only the JPEG data
                        logger.info(
                            f"Found JPEG signature at position {signature_pos}, stripping prefix bytes"
                        )
                        frame_data = frame_data[signature_pos:]
                    elif signature_pos == -1:
                        logger.warning("JPEG signature not found in data")

                    # Create BytesIO object from adjusted data
                    image_bytes = io.BytesIO(frame_data)
                    image = Image.open(image_bytes)

                    # Create simple metadata with frame number
                    metadata = {"frame_number": frame_number}

                    # Save metadata to JSON file
                    with open(
                        os.path.join(device_folder, "json", f"{base_filename}.json"),
                        "w",
                    ) as f:
                        # Use ensure_ascii=False to handle unicode properly
                        # Use separators without extra spaces to ensure consistent formatting
                        json.dump(
                            metadata, f, ensure_ascii=False, separators=(",", ":")
                        )

                    # Create frames directory and save image
                    os.makedirs(os.path.join(device_folder, "frames"), exist_ok=True)

                    # Save image
                    image.save(
                        os.path.join(device_folder, "frames", f"{base_filename}.jpg"),
                        "JPEG",
                    )

                    # Only increment the counter for auto-numbered frames
                    if frame_number is None:
                        self.frames_buffer[device_id][timestamp] += 1
                    else:
                        # Update the counter to be at least as high as the highest frame number
                        self.frames_buffer[device_id][timestamp] = max(
                            self.frames_buffer[device_id][timestamp], frame_number + 1
                        )

                    self.last_frame_times[(device_id, timestamp)] = time.time()

                except Image.UnidentifiedImageError as ex:
                    logger.info(f"Frame data length: {len(frame_data)}")
                    logger.info(f"First few bytes: {frame_data[:20]}")

                    # As a last resort, try to find another format signature
                    try:
                        # Try looking for alternative image signatures and retry
                        retry_success = False

                        # Try with the larger JPEG signature
                        jpeg_full_signature = b"\xff\xd8\xff\xe0\x00\x10JFIF"
                        signature_pos = frame_data.find(jpeg_full_signature)
                        if signature_pos > 0:
                            # Try again with more precise signature
                            retry_data = frame_data[signature_pos:]
                            image_bytes = io.BytesIO(retry_data)
                            image = Image.open(image_bytes)

                            # Save image directly without EXIF
                            os.makedirs(
                                os.path.join(device_folder, "frames"), exist_ok=True
                            )
                            image.save(
                                os.path.join(
                                    device_folder, "frames", f"{base_filename}.jpg"
                                ),
                                "JPEG",
                            )

                            # Create basic metadata
                            metadata = {
                                "frame_number": frame_number,
                                "timestamp": time.time(),
                            }
                            with open(
                                os.path.join(
                                    device_folder, "json", f"{base_filename}.json"
                                ),
                                "w",
                            ) as f:
                                json.dump(
                                    metadata,
                                    f,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                )

                            logger.info(
                                f"Successfully recovered frame with full JPEG signature detection"
                            )
                            retry_success = True

                        if not retry_success:
                            logger.error(f"Could not recover image data: {ex}")

                    except Exception as retry_ex:
                        logger.error(f"Recovery attempt failed: {retry_ex}")

                finally:
                    if "image_bytes" in locals():
                        image_bytes.close()

        except Exception as e:
            logger.exception(f"Error handling frame: {e}")

    def handle_frame_batch(self, device_id, timestamp, frames_batch):
        """
        Handle a batch of frames with frame_number and image_base64 directly in the payload

        Args:
            device_id: The device ID
            timestamp: The session timestamp
            frames_batch: A list of dicts, each with frame_number and image_base64 fields
        """
        try:
            logger.info(
                f"Processing batch of {len(frames_batch)} frames from device {device_id}"
            )

            processed_count = 0
            for frame_data in frames_batch:
                try:
                    # Extract frame number and image data from the frame object
                    if (
                        "frame_number" not in frame_data
                        or "image_base64" not in frame_data
                    ):
                        logger.error(
                            f"Missing required fields in frame data: {frame_data.keys()}"
                        )
                        continue

                    frame_number = frame_data["frame_number"]
                    image_base64 = frame_data["image_base64"]

                    # Process the individual frame
                    self.handle_frame_base64(
                        device_id, timestamp, image_base64, frame_number
                    )
                    processed_count += 1

                except Exception as e:
                    logger.error(
                        f"Error processing frame {frame_data.get('frame_number')}: {e}"
                    )

            logger.info(
                f"Successfully processed {processed_count} out of {len(frames_batch)} frames"
            )

        except Exception as e:
            logger.exception(f"Error handling frame batch: {e}")

    def collect_jpg_files(self, base_folder):
        jpg_files = []
        for root, _, files in os.walk(base_folder):
            for file in files:
                if file.lower().endswith(".jpg"):
                    jpg_files.append(os.path.join(root, file))
        return sorted(jpg_files)

    def _create_video(self, device_id, timestamp):
        try:
            folder_path = os.path.join(self.base_output_folder, device_id, timestamp)
            frames = sorted([f for f in os.listdir(folder_path) if f.endswith(".jpg")])
            if not frames:
                return

            # Read first frame for dimensions
            first_frame = cv2.imread(os.path.join(folder_path, frames[0]))
            height, width = first_frame.shape[:2]

            # Create video
            output_path = os.path.join(folder_path, "output.avi")
            fourcc = cv2.VideoWriter_fourcc("F", "M", "P", "4")
            out = cv2.VideoWriter(output_path, fourcc, 30.0, (width, height))

            # Add frames to video
            for frame_file in frames:
                frame_path = os.path.join(folder_path, frame_file)
                frame = cv2.imread(frame_path)
                out.write(frame)

            out.release()

            s3util.upload_file(
                file_location=output_path, key=output_path.replace("\\", "/")
            )

            url = s3util.generate_presigned_url(
                object_key=output_path.replace("\\", "/"),
                expiry=os.getenv("S3_SIGNED_URL_EXPIRY", 604800),
            )
            logger.info(f"Video created at {output_path}")

            logger.info("cleaning up frames ...")
            for frame_file in frames:
                frame_path = os.path.join(folder_path, frame_file)
                if not frame_path.endswith(".avi"):
                    os.remove(frame_path)

            self._update_video_table(device_id=device_id, video_path=url)

        except Exception as e:
            logger.exception(f"Error creating video: {e}")
        finally:
            # Clean up
            del self.frames_buffer[device_id][timestamp]
            del self.last_frame_times[(device_id, timestamp)]

    def _merge_json_files(self, device_id, timestamp):
        try:
            device_folder = os.path.join(self.base_output_folder, device_id, timestamp)

            if not os.path.exists(device_folder):
                return

            # Collect all JSON data
            all_data = []

            # First read master.json if it exists
            master_file = os.path.join(device_folder, "master.json")
            if os.path.exists(master_file):
                with open(master_file, "r") as f:
                    all_data = json.load(f)

            # Read all temporary files
            temp_files = [f for f in os.listdir(device_folder) if f.endswith(".json")]
            for temp_file in temp_files:
                file_path = os.path.join(device_folder, temp_file)
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        all_data.append(data)
                    # Delete temp file after reading
                    # os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error processing temp file {file_path}: {e}")
                    continue

            if all_data:
                # Sort by timestamp
                all_data.sort(key=lambda x: x.get("timestamp", 0))

                # Write updated master file
                with open(master_file, "w") as f:
                    json.dump(all_data, f, ensure_ascii=False, separators=(",", ":"))

            logger.info(
                f"Merged JSON files for device {device_id}, timestamp {timestamp}"
            )

            logger.info("cleaning up temp json files ...")
            for temp_file in temp_files:
                file_path = os.path.join(device_folder, temp_file)
                if not file_path.startswith("master"):
                    os.remove(file_path)

        except Exception as e:
            logger.exception(f"Error merging JSON files: {e}")

    def _monitor_streams(self):
        while self.running:
            try:
                current_time = time.time()
                with self.lock:
                    for (device_id, timestamp), last_time in list(
                        self.last_frame_times.items()
                    ):
                        if current_time - last_time > self.stream_timeout:
                            logger.info("stream timeout after 60 seconds")

            except Exception as e:
                logger.error(f"Error monitoring streams: {e}")

            time.sleep(1)

    def _update_video_table(self, device_id, video_path):
        try:
            # fetch functional token
            # create video
            request_body = {"email": "functional_user@curium.life", "otp": "1234"}
            response = requests.post(
                "http://127.0.0.1:7050/api/auth/verify",
                json=request_body,
            )
            response_body = response.json()
            token = response_body["tokens"]["access"]
            video_request_body = {
                "exercise_type": "peanut",
                "retain": True,
                "video_path": video_path,
                "performer": device_id,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "device-id": device_id,
            }
            video_response = requests.post(
                "http://127.0.0.1:7050/api/video",
                headers=headers,
                json=video_request_body,
            )
            return video_response.json()
        except Exception as e:
            logger.exception(f"Error updating video table: {e}")
            return None

    def stop(self):
        self.running = False


class MQTTHandler:
    def __init__(
        self,
        broker_address,
        base_output_folder,
        broker_port=8883,
        cert_path="certificates",
        username="admin",
        password="letmein",
    ):
        self.base_output_folder = base_output_folder
        self.video_handler = VideoStreamHandler(
            base_output_folder=self.base_output_folder
        )
        self.client = mqtt_client.Client()
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.username = username
        self.password = password

        # Setup TLS if certificate path exists
        if os.path.exists(cert_path):
            try:
                self._setup_tls(cert_path)
            except Exception as e:
                logger.error(f"Failed to setup TLS: {e}")
                # Fall back to username/password only
                if username and password:
                    self.client.username_pw_set(username, password)
        elif username and password:
            self.client.username_pw_set(username, password)

        self._setup_callbacks()

    def _setup_tls(self, cert_path):
        self.client.tls_set(
            ca_certs=f"{cert_path}/ca.crt",
            certfile=f"{cert_path}/device/client.crt",
            keyfile=f"{cert_path}/device/client.key",
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )
        self.client.tls_insecure_set(True)
        self.client.username_pw_set(self.username, self.password)

    def _setup_callbacks(self):
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info("Connected to MQTT broker")
                # Subscribe to video frame topics
                client.subscribe("video/stream/+/+/frame")
            else:
                logger.error(f"Connection failed with code {rc}")

        def on_message(client, userdata, msg):
            try:
                # Topic format: video/stream/device_id/timestamp/[frame|json]
                parts = msg.topic.split("/")
                device_id, timestamp = parts[2], parts[3]
                message_type = parts[4]

                if message_type == "frame":
                    # Flag to track if the message was processed by any handler
                    message_processed = False

                    # Try to parse as JSON first to check if it's the new batch format
                    try:
                        payload_str = msg.payload.decode("utf-8")
                        payload_data = json.loads(payload_str)

                        # Check if it's a list (new batch format with frame_number)
                        if isinstance(payload_data, list) and not message_processed:
                            # Check if the list items have frame_number and image_base64 fields
                            if (
                                len(payload_data) > 0
                                and "frame_number" in payload_data[0]
                                and "image_base64" in payload_data[0]
                            ):
                                logger.info(
                                    f"Received batch of {len(payload_data)} frames with new format from device {device_id}"
                                )
                                self.video_handler.handle_frame_batch(
                                    device_id, timestamp, payload_data
                                )
                                message_processed = True
                                return  # Exit to prevent double processing

                        # Check if it's a dictionary (previous batch format)
                        if isinstance(payload_data, dict) and not message_processed:
                            # Check if it has the previous batch format
                            has_frame_number_format = any(
                                key.startswith("frame_number_")
                                for key in payload_data.keys()
                            )

                            if has_frame_number_format:
                                logger.info(
                                    f"Received batch of {len(payload_data)} frames with frame_number_X format from device {device_id}"
                                )
                                self._process_frame_batch(
                                    device_id, timestamp, payload_data
                                )
                                message_processed = True
                                return  # Exit to prevent double processing

                            # Check if the keys are numeric (older format)
                            try:
                                # Try to convert at least one key to int to check format
                                int(next(iter(payload_data.keys())))
                                logger.info(
                                    f"Received batch with numeric keys from device {device_id}"
                                )
                                # Process using older numeric key format
                                self._process_numeric_frame_batch(
                                    device_id, timestamp, payload_data
                                )
                                message_processed = True
                                return  # Exit to prevent double processing
                            except (ValueError, StopIteration):
                                # Not our expected format, continue to handle as single frame
                                pass

                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Not JSON, treat as single base64 frame
                        pass

                    # If we get here, it's a single frame or unrecognized format that wasn't processed yet
                    if not message_processed:
                        logger.info(
                            f"Processing as single frame from device {device_id}"
                        )
                        try:
                            # Make sure the payload is valid base64 by padding if necessary
                            payload = msg.payload
                            if isinstance(payload, bytes):
                                try:
                                    payload = payload.decode("utf-8")
                                except UnicodeDecodeError:
                                    # If it can't be decoded as utf-8, it's likely already binary
                                    pass

                            # Add padding if needed (ensure length is multiple of 4)
                            if isinstance(payload, str):
                                # Check if we need to add padding
                                padding_needed = len(payload) % 4
                                if padding_needed > 0:
                                    logger.info(
                                        f"Adding {4 - padding_needed} padding characters to base64 string"
                                    )
                                    payload += "=" * (4 - padding_needed)

                            self.video_handler.handle_frame_base64(
                                device_id, timestamp, payload
                            )
                        except Exception as e:
                            logger.error(f"Error processing single frame: {e}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                logger.exception(e)

        self.client.on_connect = on_connect
        self.client.on_message = on_message

    def _process_frame_batch(self, device_id, timestamp, frame_batch):
        """Process a batch of frames with keys in format 'frame_number_X'"""
        # Validate the batch
        valid_batch = True
        error_msg = ""
        frame_count = 0

        # Check for expected key format and extract frame numbers
        for key in frame_batch.keys():
            if not key.startswith("frame_number_"):
                logger.warning(f"Invalid key format: {key}, expected 'frame_number_X'")
                valid_batch = False
                error_msg = f"Invalid key format: {key}, expected 'frame_number_X'"
                break

            # Extract the number part
            try:
                frame_number = int(key.replace("frame_number_", ""))
            except ValueError:
                logger.warning(f"Could not extract frame number from key: {key}")
                valid_batch = False
                error_msg = f"Could not extract frame number from key: {key}"
                break

            # Check if the value is a string (base64 data)
            if not isinstance(frame_batch[key], str):
                valid_batch = False
                error_msg = f"Frame data for {key} is not a string"
                break

        if not valid_batch:
            logger.error(f"Invalid frame batch: {error_msg}")
            return

        logger.info(
            f"Processing batch of {len(frame_batch)} frames from device {device_id}"
        )

        # Process each frame in the batch
        for key, frame_data in frame_batch.items():
            try:
                # Extract frame number from key
                frame_number = int(key.replace("frame_number_", ""))

                self.video_handler.handle_frame_base64(
                    device_id, timestamp, frame_data, frame_number=frame_number
                )
                frame_count += 1
            except Exception as e:
                logger.error(f"Error processing frame {key}: {e}")

        logger.info(f"Successfully processed {frame_count} frames from batch")

    def _process_numeric_frame_batch(self, device_id, timestamp, frame_batch):
        """Process a batch of frames with numeric keys (e.g., "1", "2", "3")"""
        # Validate the batch
        valid_batch = True
        error_msg = ""

        # Check if all keys can be parsed as integers
        for key in frame_batch.keys():
            try:
                int(key)
            except ValueError:
                valid_batch = False
                error_msg = f"Invalid frame number format: {key}"
                break

        # Check if all values are strings (base64 data)
        if valid_batch:
            for key, value in frame_batch.items():
                if not isinstance(value, str):
                    valid_batch = False
                    error_msg = f"Frame data for frame {key} is not a string"
                    break

        if not valid_batch:
            logger.error(f"Invalid frame batch: {error_msg}")
            return

        # Process each frame in the batch
        frame_count = 0
        for frame_number, frame_data in frame_batch.items():
            try:
                self.video_handler.handle_frame_base64(
                    device_id, timestamp, frame_data, frame_number=int(frame_number)
                )
                frame_count += 1
            except Exception as e:
                logger.error(f"Error processing frame {frame_number}: {e}")

        logger.info(f"Successfully processed {frame_count} frames from numeric batch")

    def start(self):
        try:
            self.client.connect(self.broker_address, self.broker_port)
            self.client.loop_forever()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.exception(f"Error in MQTT handler: {e}")
            self.stop()

    def stop(self):
        self.video_handler.stop()
        self.client.loop_stop()
        self.client.disconnect()
