from django.db import models
import uuid

class Video(models.Model):
    # video_id is a UUID field and also the primary key for the model
    video_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)

    # Correct reference to the 'User' model from the 'user' app, with explicit column name
    uploaded_by = models.ForeignKey(
        'user.User',
        on_delete=models.CASCADE,
        to_field='id',
        db_column='uploaded_by'
    )

    # upload_date is a timestamp field, automatically set when the video is uploaded
    upload_date = models.DateTimeField(auto_now_add=True)

    # exercise_type is a varchar (CharField in Django)
    exercise_type = models.CharField(max_length=255)

    # performer is a varchar for the name of the person performing the exercise
    performer = models.CharField(max_length=255)

    # retain is a boolean to specify whether to keep the video or not
    retain = models.BooleanField(default=True)

    # video_path is a varchar (CharField) for storing the file path or URL of the video
    video_path = models.CharField(max_length=1024)

    def __str__(self):
        return f"Video {self.video_id} by {self.performer} for {self.exercise_type}"

    class Meta:
        verbose_name = "Video"
        verbose_name_plural = "Videos"
        db_table = 'video'
