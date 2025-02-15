from rest_framework import serializers
from .models import ProcessedFrame
from PIL import Image
from PIL.ExifTags import TAGS
import json


class ProcessedFrameSerializer(serializers.ModelSerializer):
    frame_file = serializers.ImageField(write_only=True)

    class Meta:
        model = ProcessedFrame
        fields = ("processed_frame_id", "device_id", "frame_number", "frame_file")
        read_only_fields = ("processed_frame_id", "frame_path", "json_path")

    def validate(self, data):
        try:
            image = Image.open(data["frame_file"])
            exif = image._getexif()
            if not exif:
                raise serializers.ValidationError("No EXIF data found in image")

            # Extract JSON from EXIF
            json_data = None
            for tag_id in exif:
                tag = TAGS.get(tag_id, tag_id)
                if tag == "UserComment":  # Adjust based on where you store the JSON
                    json_data = json.loads(exif[tag_id])
                    break

            if not json_data or "frame_number" not in json_data:
                raise serializers.ValidationError("Frame number not found in EXIF data")

            data["frame_number"] = json_data["frame_number"]
            return data
        except Exception as e:
            raise serializers.ValidationError(f"Error processing image: {str(e)}")
