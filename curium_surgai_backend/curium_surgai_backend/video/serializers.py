from rest_framework import serializers
from .models import Video
from device.models import Device


class VideoSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Video
        fields = (
            "video_id",
            "uploaded_by",
            "upload_date",
            "last_modified_date",
            "exercise_type",
            "performer",
            "retain",
            "video_path",
        )
        read_only_fields = ("video_id", "upload_date", "last_modified_date")

    def save(self):
        device_id = self.context["request"].headers.get("deviceid")
        device = Device.objects.get(device_id=device_id)
        exercise_type = self.validated_data.get("exercise_type", None)
        performer = self.validated_data.get("performer", None)
        retain = self.validated_data.get("retain", False)
        video_path = self.validated_data.get("video_path", None)
        volume = Video(
            uploaded_by=device,
            exercise_type=exercise_type,
            performer=performer,
            retain=retain,
            video_path=video_path,
        )
        volume.save()
        return volume
