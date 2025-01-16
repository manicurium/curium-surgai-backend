from rest_framework import serializers
from .models import Device


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["device_id", "mac_address", "mqtt_topic", "is_active", "created_at"]
        read_only_fields = ["mqtt_topic"]

    def create(self, validated_data):
        # Generate unique MQTT topic for the device
        request_context = self.context["request"]
        mqtt_topic = f"video/{request_context.user.id}/{validated_data['mac_address']}"
        validated_data["mqtt_topic"] = mqtt_topic
        return super().create(validated_data)
