import cv2
import numpy as np
import os
import threading
import time
import logging
from paho.mqtt import client as mqtt_client
import ssl
from collections import defaultdict

logger = logging.getLogger(__name__)


class VideoStreamHandler:
    def __init__(self, base_output_folder="received_frames", stream_timeout=10):
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
                os.remove(frame_path)  # Delete frame after adding to video

            out.release()
            logging.info(f"Video created at {output_path}")

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

    def stop(self):
        self.running = False
        self.monitor_thread.join()


class MQTTVideoSubscriber:
    def __init__(
        self,
        broker_address,
        broker_port=8883,
        topic="video/stream",
        cert_path="certificates",
        username="admin",
        password="letmein",
    ):
        self.client = mqtt_client.Client()
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.topic = topic
        self.username = username
        self.password = password
        self.video_handler = VideoStreamHandler()

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
                client.subscribe(f"{self.topic}/+/+/frame")
            else:
                logger.error(f"Connection failed with code {rc}")

        def on_message(client, userdata, msg):
            try:
                # Topic format: video/stream/device_id/timestamp/frame
                parts = msg.topic.split("/")
                device_id, timestamp = parts[2], parts[3]
                self.video_handler.handle_frame(device_id, timestamp, msg.payload)
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
            logger.error(f"Error in subscriber: {e}")
            self.stop()

    def stop(self):
        self.video_handler.stop()
        self.client.loop_stop()
        self.client.disconnect()


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     subscriber = MQTTVideoSubscriber("127.0.0.1")
#     subscriber.start()
