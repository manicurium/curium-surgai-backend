from django.db import models
import uuid
from video.models import Video


class ProcessedFrame(models.Model):
    processed_frame_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    video = models.ForeignKey(
        Video, on_delete=models.CASCADE, related_name="processed_frames"
    )
    collated_json = models.JSONField()  # Use models.JSONField for Django 3.1+

    class Meta:
        db_table = "surgai_frame"
