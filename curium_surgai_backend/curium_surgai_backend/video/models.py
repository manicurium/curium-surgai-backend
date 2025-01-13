from django.db import models
import uuid
from django.conf import settings


class Video(models.Model):
    video_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(
        "user.User",
        on_delete=models.CASCADE,
        related_name="uploaded_videos",
    )
    upload_date = models.DateTimeField(auto_now_add=True)
    exercise_type = models.CharField(max_length=100)
    performer = models.CharField(max_length=100)
    retain = models.BooleanField(default=True)
    video_path = models.CharField(max_length=255)

    class Meta:
        db_table = "surgai_video"
