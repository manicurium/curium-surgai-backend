from django.db import models
import uuid
from video.models import Video


class ProcessedFrame(models.Model):
    processed_frame_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    device_id = models.ForeignKey(
        "device.Device",
        on_delete=models.CASCADE,
        related_name="uploaded_frame",
    )
    frame_number = models.IntegerField()
    frame_path = models.CharField(max_length=255)
    json_path = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "surgai_frame"
        ordering = ["frame_number"]
        # Ensure unique frame numbers per device
        unique_together = ["device_id", "frame_number"]
