from rest_framework import serializers
from .models import Video

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['video_id', 'uploaded_by', 'upload_date', 'exercise_type', 'performer', 'retain', 'video_path']
        read_only_fields = ['video_id', 'upload_date']  # These fields are auto-generated