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

logger = logging.getLogger(__name__)


class JSONStreamHandler:
    def __init__(self, base_output_folder="received_json", batch_timeout=60):
        self.base_output_folder = base_output_folder
        self.batch_timeout = batch_timeout
        self.json_buffer = defaultdict(
            lambda: defaultdict(list)
        )  # {device_id: {timestamp: [json_messages]}}
        self.last_message_times = {}  # {(device_id, timestamp): last_message_time}
        self.lock = threading.Lock()
        self.running = True

        os.makedirs(base_output_folder, exist_ok=True)
        self.monitor_thread = threading.Thread(target=self._monitor_json_streams)
        self.monitor_thread.start()

    def handle_json(self, device_id, timestamp, json_data):
        try:
            with self.lock:
                # Parse JSON data if it's in string format
                if isinstance(json_data, (str, bytes)):
                    json_data = json.loads(json_data)

                # Add timestamp if not present
                if "timestamp" not in json_data:
                    json_data["timestamp"] = time.time()

                # Create device/timestamp folder structure
                device_folder = os.path.join(
                    self.base_output_folder, device_id, timestamp
                )
                os.makedirs(device_folder, exist_ok=True)

                # Get next sequence number for temp file
                existing_temp_files = [
                    f for f in os.listdir(device_folder) if f.startswith("temp_")
                ]
                next_seq = len(existing_temp_files) + 1
                temp_file = os.path.join(device_folder, f"temp_{next_seq:04d}.json")
                with open(temp_file, "w") as f:
                    json.dump(json_data, f)

                self.last_message_times[(device_id, timestamp)] = time.time()

        except Exception as e:
            logger.exception(f"Error handling JSON message: {e}")

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
            temp_files = [f for f in os.listdir(device_folder) if f.startswith("temp_")]
            for temp_file in temp_files:
                file_path = os.path.join(device_folder, temp_file)
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        all_data.append(data)
                    # Delete temp file after reading
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error processing temp file {file_path}: {e}")
                    continue

            if all_data:
                # Sort by timestamp
                all_data.sort(key=lambda x: x.get("timestamp", 0))

                # Write updated master file
                with open(master_file, "w") as f:
                    json.dump(all_data, f, indent=2)

            logger.info(
                f"Merged JSON files for device {device_id}, timestamp {timestamp}"
            )

        except Exception as e:
            logger.exception(f"Error merging JSON files: {e}")

    def _monitor_json_streams(self):
        while self.running:
            try:
                current_time = time.time()
                with self.lock:
                    for (device_id, timestamp), last_time in list(
                        self.last_message_times.items()
                    ):
                        if current_time - last_time > self.batch_timeout:
                            self._merge_json_files(device_id, timestamp)
                            del self.last_message_times[(device_id, timestamp)]

            except Exception as e:
                logger.error(f"Error monitoring JSON streams: {e}")

            time.sleep(1)

    def stop(self):
        self.running = False
        self.monitor_thread.join()

    # def stop(self):
    #     self.running = False
    #     # Save any remaining data
    #     for device_id in list(self.json_buffer.keys()):
    #         for timestamp in list(self.json_buffer[device_id].keys()):
    #             self._save_json_batch(device_id, timestamp)
    #     self.monitor_thread.join()


class VideoStreamHandler:
    def __init__(self, base_output_folder="received_frames", stream_timeout=60):
        self.base_output_folder = base_output_folder
        self.stream_timeout = stream_timeout
        self.frames_buffer = defaultdict(dict)  # {device_id: {timestamp: frame_count}}
        self.last_frame_times = {}  # {(device_id, timestamp): last_frame_time}
        self.lock = threading.Lock()
        self.running = True

        os.makedirs(base_output_folder, exist_ok=True)
        self.monitor_thread = threading.Thread(target=self._monitor_streams)
        self.monitor_thread.start()

    def handle_frame(self, device_id, timestamp, frame_data):
        try:
            with self.lock:
                if timestamp not in self.frames_buffer[device_id]:
                    self.frames_buffer[device_id][timestamp] = 0

                frame_count = self.frames_buffer[device_id][timestamp]
                self.frames_buffer[device_id][timestamp] += 1

                # Save frame
                device_folder = os.path.join(
                    self.base_output_folder, device_id, timestamp
                )
                os.makedirs(device_folder, exist_ok=True)
                filename = f"frame_{frame_count:06d}.jpg"
                frame = cv2.imdecode(
                    np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR
                )
                cv2.imwrite(os.path.join(device_folder, filename), frame)

                self.last_frame_times[(device_id, timestamp)] = time.time()

        except Exception as e:
            logger.exception(f"Error handling frame: {e}")

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
                if os.path.exists(frame_path):
                    os.remove(frame_path)

            out.release()
            logger.info(f"Video created at {output_path}")
            self._update_video_table(device_id=device_id, video_path=output_path)

        except Exception as e:
            logger.exception(f"Error creating video: {e}")
        finally:
            # Clean up
            del self.frames_buffer[device_id][timestamp]
            del self.last_frame_times[(device_id, timestamp)]

    def _monitor_streams(self):
        while self.running:
            try:
                current_time = time.time()
                with self.lock:
                    for (device_id, timestamp), last_time in list(
                        self.last_frame_times.items()
                    ):
                        if current_time - last_time > self.stream_timeout:
                            self._create_video(device_id, timestamp)

            except Exception as e:
                logger.error(f"Error monitoring streams: {e}")

            time.sleep(1)

    def _update_video_table(self, device_id, video_path):
        try:
            # fetch functional token
            # create video
            request_body = {"email": "functional_user@curium.life", "otp": "1236"}
            response = requests.post(
                "http://127.0.0.1:7050/api/auth/verify",
                json=request_body,
            )
            response_body = response.json()
            # logger.info(f"token response: {response}")
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
                "deviceid": device_id,
            }
            video_response = requests.post(
                "http://127.0.0.1:7050/api/video",
                headers=headers,
                json=video_request_body,
            )
            # logger.info(f"Video record: {video_response.json()}")
            return video_response.json()
        except Exception as e:
            logger.exception(f"Error updating video table: {e}")
            return None

    def stop(self):
        self.running = False
        self.monitor_thread.join()


class MQTTHandler:
    def __init__(
        self,
        broker_address,
        broker_port=8883,
        cert_path="certificates",
        username="admin",
        password="letmein",
    ):
        self.video_handler = VideoStreamHandler()
        self.json_handler = JSONStreamHandler()
        self.client = mqtt_client.Client()
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.username = username
        self.password = password

        self._setup_tls(cert_path)
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
                # Subscribe to both video frame and JSON topics
                client.subscribe("video/stream/+/+/frame")
                client.subscribe("video/stream/+/+/json")
            else:
                logger.error(f"Connection failed with code {rc}")

        def on_message(client, userdata, msg):
            try:
                # Topic format: video/stream/device_id/timestamp/[frame|json]
                parts = msg.topic.split("/")
                device_id, timestamp = parts[2], parts[3]
                message_type = parts[4]

                if message_type == "frame":
                    self.video_handler.handle_frame(device_id, timestamp, msg.payload)
                elif message_type == "json":
                    self.json_handler.handle_json(device_id, timestamp, msg.payload)
            except Exception as e:
                logger.error(f"Error processing message: {e}")

        self.client.on_connect = on_connect
        self.client.on_message = on_message

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
        self.json_handler.stop()
        self.client.loop_stop()
        self.client.disconnect()
