from django.apps import AppConfig


class VideoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "video"


class UserConfig(AppConfig):
    name = "user"
    default_auto_field = "django.db.models.BigAutoField"
