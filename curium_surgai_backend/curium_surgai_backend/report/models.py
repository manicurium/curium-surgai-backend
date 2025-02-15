from django.db import models
import uuid
from video.models import Video


class Report(models.Model):
    report_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name="reports")
    report_date = models.DateTimeField(auto_now_add=True)
    report_json = models.JSONField()  # Use models.JSONField for Django 3.1+
    score = models.JSONField(blank=True)

    class Meta:
        db_table = "surgai_report"
