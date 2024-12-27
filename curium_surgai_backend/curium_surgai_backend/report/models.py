from django.db import models
import uuid

class Report(models.Model):
    report_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)

    # ForeignKey to the Video model, explicitly setting the column name to 'video_id'
    video_id = models.ForeignKey(
        'video.Video',
        on_delete=models.CASCADE,
        to_field='video_id',
        db_column='video_id'
    )

    report_date = models.DateTimeField(auto_now_add=True)  # Auto-generated timestamp for when the report is created
    report_json = models.JSONField()  # JSON type to store report data

    def __str__(self):
        return f"Report {self.report_id} for Video {self.video_id}"

    class Meta:
        verbose_name = "Report"
        verbose_name_plural = "Reports"
        db_table = 'report'
