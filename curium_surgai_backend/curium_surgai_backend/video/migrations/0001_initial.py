# Generated by Django 5.0.4 on 2024-12-26 14:00

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Video',
            fields=[
                ('video_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('upload_date', models.DateTimeField(auto_now_add=True)),
                ('exercise_type', models.CharField(max_length=255)),
                ('performer', models.CharField(max_length=255)),
                ('retain', models.BooleanField(default=True)),
                ('video_path', models.CharField(max_length=1024)),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Video',
                'verbose_name_plural': 'Videos',
            },
        ),
    ]
