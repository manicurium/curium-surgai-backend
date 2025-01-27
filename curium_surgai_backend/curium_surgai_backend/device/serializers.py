from rest_framework import serializers
from .models import Device


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = [
            "device_id",
            "mac_address",
            "mqtt_publish_topic",
            "mqtt_listener_topic",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["mqtt_publish_topic", "mqtt_listener_topic"]

    def create(self, validated_data):
        # Generate unique MQTT topic for the device
        device = Device(**validated_data)
        device.save()

        mqtt_publish_topic = f"video/stream/{device.device_id}"
        mqtt_listener_topic = f"video/result/{device.device_id}"
        device.mqtt_publish_topic = mqtt_publish_topic
        device.mqtt_listener_topic = mqtt_listener_topic
        device.save()
        return device
