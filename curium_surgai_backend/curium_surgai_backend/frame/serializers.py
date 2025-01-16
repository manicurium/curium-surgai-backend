from rest_framework import serializers
from .models import ProcessedFrame


class ProcessedFrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessedFrame
        fields = ("processed_frame_id", "video", "collated_json")
        read_only_fields = ("processed_frame_id",)
