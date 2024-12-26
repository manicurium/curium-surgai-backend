from rest_framework import serializers
from .models import Frame

class FrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Frame
        fields = ['processed_frame_id', 'video_id', 'collated_json']
        read_only_fields = ['processed_frame_id']  # processed_frame_id is auto-generated
