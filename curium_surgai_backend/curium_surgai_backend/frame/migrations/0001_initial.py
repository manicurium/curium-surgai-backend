# Generated by Django 5.0.4 on 2024-12-27 13:46

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('video', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Frame',
            fields=[
                ('processed_frame_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('collated_json', models.JSONField()),
                ('video_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='video.video')),
            ],
            options={
                'verbose_name': 'Frame',
                'verbose_name_plural': 'Frames',
                'db_table': 'frame',
            },
        ),
    ]
