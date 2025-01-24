import cv2
from paho.mqtt import client as mqtt_client
import numpy as np
import json
import os
from datetime import datetime
from collections import defaultdict
import threading
from queue import Queue
import time
import logging
from django.conf import settings
import ssl

logger = logging.getLogger()

logger.setLevel(logging.DEBUG)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


class DeviceStreamTracker:
    """Track statistics and status for each device stream"""

    def __init__(self, device_id, video_info=None):
        self.device_id = device_id
        self.video_info = video_info
        self.frames_received = 0
        self.last_frame_time = None
        self.start_time = datetime.now()
        self.status = "active"
        self.frames_buffer = {}
        self.metadata_queue = Queue()

    def update_stats(self):
        self.frames_received += 1
        self.last_frame_time = datetime.now()

    def get_status_report(self):
        current_time = datetime.now()
        time_since_last_frame = (
            (current_time - self.last_frame_time).seconds if self.last_frame_time else 0
        )

        return {
            "device_id": self.device_id,
            "frames_received": self.frames_received,
            "stream_duration": str(current_time - self.start_time),
            "status": "inactive" if time_since_last_frame > 10 else "active",
            "video_info": self.video_info,
        }


class MultiDeviceVideoSubscriber:
    def __init__(
        self,
        broker_address="127.0.0.1",
        broker_port=1883,
        topic="video/stream",
        stream_timeout=20,
        base_output_folder=os.path.join(settings.MEDIA_ROOT, "received_frames"),
        username=None,
        password=None,
    ):
        self.client = mqtt_client.Client()
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.topic = topic
        self.base_output_folder = base_output_folder
        self.username = username
        self.password = password
        self.stream_timeout = stream_timeout

        # Create base output folder
        os.makedirs(base_output_folder, exist_ok=True)

        # Dictionary to track each device's stream
        self.device_trackers = {}
        self.active_streams = {}
        # Lock for thread-safe operations
        self.lock = threading.Lock()
        # Start status monitoring thread
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_streams)

        self.setup_mqtt()

    def setup_mqtt(self):
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logging.debug("Connected to MQTT Broker!")
                # Subscribe to both metadata and frame topics
                client.subscribe(f"{self.topic}/+/metadata")
                client.subscribe(f"{self.topic}/+/frame")
            else:
                logging.debug(f"Failed to connect, return code {rc}")

        def on_message(client, userdata, msg):
            try:
                # Extract device ID from topic
                # Expected format: video/stream/{device_id}/metadata or video/stream/{device_id}/frame
                parts = msg.topic.split("/")
                logger.debug(f"parts {parts}")
                device_id, timestamp = parts[2], parts[3]
                logger.debug(f"{device_id},: {timestamp}")
                if msg.topic.endswith("/metadata"):
                    self.handle_metadata(device_id, timestamp, msg.payload)
                elif msg.topic.endswith("/frame"):
                    self.handle_frame(device_id, timestamp, msg.payload)
            except Exception as e:
                logging.debug(f"Error processing message: {e}")

        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.tls_set(
            ca_certs="certificates/ca.crt",  # CA cert to verify server
            certfile="certificates/device/client.crt",  # Client's certificate
            keyfile="certificates/device/client.key",  # Client's private key
            cert_reqs=ssl.CERT_REQUIRED,  # Verify server certificate
            tls_version=ssl.PROTOCOL_TLSv1_2,  # Use TLS protocol
        )  # Default cipher suite
        self.client.tls_insecure_set(True)

        self.client.on_connect = on_connect
        self.client.on_message = on_message

    def get_device_tracker(self, device_id, timestamp, video_info=None):
        """Get or create device tracker"""
        with self.lock:
            if device_id not in self.device_trackers:
                # Create timestamp-based subdirectory for new stream

                device_folder = os.path.join(
                    self.base_output_folder, device_id, timestamp
                )
                os.makedirs(device_folder, exist_ok=True)

                # Create new tracker
                self.device_trackers[device_id] = DeviceStreamTracker(
                    device_id, video_info
                )
                logging.debug(f"New device detected: {device_id}")
                if video_info:
                    logging.debug(f"Video info: {json.dumps(video_info, indent=2)}")

            return self.device_trackers[device_id]

    def handle_metadata(self, device_id, timestamp, payload):
        """Handle incoming metadata message"""
        try:
            metadata = json.loads(payload)
            tracker = self.get_device_tracker(
                device_id, timestamp, metadata.get("video_info")
            )

            frame_id = metadata["frame_id"]
            if frame_id in tracker.frames_buffer:
                self.process_frame(
                    device_id, tracker.frames_buffer[frame_id], timestamp, metadata
                )
                del tracker.frames_buffer[frame_id]
            else:
                tracker.metadata_queue.put((frame_id, metadata))
        except Exception as e:
            logging.debug(f"Error processing metadata for device {device_id}: {e}")

    def handle_frame(self, device_id, timestamp, payload):
        """Handle incoming frame data"""
        try:
            tracker = self.get_device_tracker(device_id, timestamp)
            frame_data = np.frombuffer(payload, dtype=np.uint8)

            # Try to get corresponding metadata
            while not tracker.metadata_queue.empty():
                _, metadata = tracker.metadata_queue.get()
                self.process_frame(device_id, frame_data, timestamp, metadata)
                return

            # Store frame data if no metadata available
            tracker.frames_buffer[metadata["frame_id"]] = frame_data
        except Exception as e:
            logging.debug(f"Error processing frame for device {device_id}: {e}")

    def process_frame(self, device_id, frame_data, timestamp, metadata):
        """Process and save frame with its metadata"""
        try:

            with self.lock:
                self.active_streams[(device_id, timestamp)] = time.time()
                logging.debug(f"Updated stream time for {device_id}/{timestamp}")
            tracker = self.device_trackers[device_id]

            # Update tracker stats
            tracker.update_stats()

            # Decode the frame
            if metadata.get("encoding") == "jpg":
                frame = cv2.imdecode(frame_data, cv2.IMREAD_COLOR)

                # Resize if frame was compressed
                if "compressed_shape" in metadata:
                    frame = cv2.resize(
                        frame,
                        (metadata["original_shape"][1], metadata["original_shape"][0]),
                    )

            # Generate filename with timestamp and frame number
            frame_timestamp = datetime.fromisoformat(metadata["timestamp"])
            frame_number = metadata.get("frame_number", tracker.frames_received)
            filename = (
                f"{frame_timestamp.strftime('%Y%m%d_%H%M%S')}_frame{frame_number}.jpg"
            )

            # Save to device-specific folder
            device_folder = os.path.join(self.base_output_folder, device_id, timestamp)
            os.makedirs(device_folder, exist_ok=True)
            filepath = os.path.join(device_folder, filename)

            # Save the frame
            cv2.imwrite(filepath, frame)

            # Save metadata
            metadata_filename = f"{os.path.splitext(filename)[0]}_metadata.json"
            metadata_filepath = os.path.join(device_folder, metadata_filename)
            with open(metadata_filepath, "w") as f:
                json.dump(metadata, f, indent=4)

            # logging.debug progress if available
            if "progress_percentage" in metadata:
                logging.debug(
                    f"Device {device_id} - Progress: {metadata['progress_percentage']}%"
                )

        except Exception as e:
            logging.debug(f"Error saving frame for device {device_id}: {e}")

    def build_video(self, device_id, timestamp):
        """Build video from frames after streaming has stopped"""
        try:
            folder_path = os.path.join(self.base_output_folder, device_id, timestamp)
            frame_files = sorted(
                [f for f in os.listdir(folder_path) if f.endswith(".jpg")]
            )

            if not frame_files:
                logging.debug(f"No frames found in {folder_path}")
                return

            # Read first frame to get dimensions
            first_frame = cv2.imread(os.path.join(folder_path, frame_files[0]))
            height, width = first_frame.shape[:2]

            # Create video writer
            video_path = os.path.join(folder_path, "output.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(video_path, fourcc, 30.0, (width, height))

            # Add all frames to video
            for frame_file in frame_files:
                frame_path = os.path.join(folder_path, frame_file)
                frame = cv2.imread(frame_path)
                out.write(frame)

            out.release()
            logging.debug(f"Video created at {video_path}")

        except Exception as e:
            logging.debug(f"Error building video: {e}")

    def monitor_streams(self):
        """Monitor streams and detect when they've stopped"""
        while self.running:
            try:
                current_time = time.time()
                with self.lock:
                    completed_streams = []

                    # Debug output
                    logging.debug(f"Active streams: {self.active_streams}")

                    for stream_key, last_frame_time in list(
                        self.active_streams.items()
                    ):
                        device_id, timestamp = stream_key
                        if current_time - last_frame_time > self.stream_timeout:
                            logging.debug(
                                f"Stream timeout detected for {device_id}/{timestamp}"
                            )
                            completed_streams.append((device_id, timestamp))
                            self.build_video(device_id, timestamp)
                            del self.active_streams[stream_key]

            except Exception as e:
                logging.debug(f"Error in monitor_streams: {e}")

            time.sleep(1)

    def start(self):
        """Start the subscriber"""
        try:
            # Start monitoring thread
            self.monitor_thread.start()

            # Connect and start MQTT loop
            self.client.connect(self.broker_address, self.broker_port)
            self.client.loop_forever()
        except KeyboardInterrupt:
            logging.debug("Stopping subscriber...")
            self.stop()
        except Exception as e:
            logging.debug(f"Error in subscriber: {e}")
            self.stop()

    def stop(self):
        """Stop the subscriber"""
        self.running = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join()
        self.client.loop_stop()
        self.client.disconnect()
