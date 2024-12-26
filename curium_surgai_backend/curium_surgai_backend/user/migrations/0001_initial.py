# Generated by Django 5.0.4 on 2024-12-26 07:41

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.UUIDField(auto_created=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('fname', models.CharField(max_length=255)),
                ('lname', models.CharField(max_length=255)),
                ('username', models.CharField(max_length=255, unique=True)),
                ('email_id', models.EmailField(max_length=254, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('role_type', models.CharField(choices=[('ADMIN', 'Admin'), ('PRACTITIONER', 'Practitioner')], default='PRACTITIONER', max_length=50)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
