from django.db import models
import uuid

class Frame(models.Model):
    # processed_frame_id is the primary key (UUID type)
    processed_frame_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)

    # video_id is a foreign key referencing the 'Video' model
    video_id = models.ForeignKey(
        'video.Video',
        on_delete=models.CASCADE,
        to_field='video_id',
        db_column='video_id'
    )

    # collated_json stores the frame data as a BLOB (Binary Large Object)
    collated_json = models.JSONField()

    def __str__(self):
        return f"Frame {self.processed_frame_id} for Video {self.video_id}"

    class Meta:
        verbose_name = "Frame"
        verbose_name_plural = "Frames"
        db_table = 'frame'  # Custom table name for the Frame model
