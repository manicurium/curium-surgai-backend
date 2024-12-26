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

logger = logging.getLogger()

logger.setLevel(logging.DEBUG)


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
        broker_address="localhost",
        broker_port=1883,
        topic="video/stream",
        base_output_folder="received_frames",
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

        # Create base output folder
        os.makedirs(base_output_folder, exist_ok=True)

        # Dictionary to track each device's stream
        self.device_trackers = {}

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
                device_id = parts[-2]

                if msg.topic.endswith("/metadata"):
                    self.handle_metadata(device_id, msg.payload)
                elif msg.topic.endswith("/frame"):
                    self.handle_frame(device_id, msg.payload)
            except Exception as e:
                logging.debug(f"Error processing message: {e}")

        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = on_connect
        self.client.on_message = on_message

    def get_device_tracker(self, device_id, video_info=None):
        """Get or create device tracker"""
        with self.lock:
            if device_id not in self.device_trackers:
                # Create device output folder
                device_folder = os.path.join(self.base_output_folder, device_id)
                os.makedirs(device_folder, exist_ok=True)

                # Create new tracker
                self.device_trackers[device_id] = DeviceStreamTracker(
                    device_id, video_info
                )
                logging.debug(f"New device detected: {device_id}")
                if video_info:
                    logging.debug(f"Video info: {json.dumps(video_info, indent=2)}")

            return self.device_trackers[device_id]

    def handle_metadata(self, device_id, payload):
        """Handle incoming metadata message"""
        try:
            metadata = json.loads(payload)
            tracker = self.get_device_tracker(device_id, metadata.get("video_info"))

            frame_id = metadata["frame_id"]
            if frame_id in tracker.frames_buffer:
                self.process_frame(device_id, tracker.frames_buffer[frame_id], metadata)
                del tracker.frames_buffer[frame_id]
            else:
                tracker.metadata_queue.put((frame_id, metadata))
        except Exception as e:
            logging.debug(f"Error processing metadata for device {device_id}: {e}")

    def handle_frame(self, device_id, payload):
        """Handle incoming frame data"""
        try:
            tracker = self.get_device_tracker(device_id)
            frame_data = np.frombuffer(payload, dtype=np.uint8)

            # Try to get corresponding metadata
            while not tracker.metadata_queue.empty():
                _, metadata = tracker.metadata_queue.get()
                self.process_frame(device_id, frame_data, metadata)
                return

            # Store frame data if no metadata available
            tracker.frames_buffer[metadata["frame_id"]] = frame_data
        except Exception as e:
            logging.debug(f"Error processing frame for device {device_id}: {e}")

    def process_frame(self, device_id, frame_data, metadata):
        """Process and save frame with its metadata"""
        try:
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
            timestamp = datetime.fromisoformat(metadata["timestamp"])
            frame_number = metadata.get("frame_number", tracker.frames_received)
            filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_frame{frame_number}.jpg"

            # Save to device-specific folder
            device_folder = os.path.join(self.base_output_folder, device_id)
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

    def monitor_streams(self):
        """Monitor active streams and report status"""
        while self.running:
            time.sleep(5)  # Check every 5 seconds
            with self.lock:
                current_time = datetime.now()
                for device_id, tracker in self.device_trackers.items():
                    status = tracker.get_status_report()
                    logging.debug(f"\nStream Status - Device {device_id}:")
                    logging.debug(json.dumps(status, indent=2))

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
        logging.debug("Subscriber stopped successfully.")