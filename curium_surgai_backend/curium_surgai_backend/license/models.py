from django.db import models
import uuid

class License(models.Model):
    license_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    org_code = models.CharField(max_length=255)  # Organization code
    device_id = models.CharField(max_length=255)  # Device identifier
    device_MAC = models.CharField(max_length=255)  # MAC address of the device
    created_at = models.DateTimeField(auto_now_add=True)  # Auto-generated timestamp
    isActive = models.BooleanField(default=True)  # Whether the license is active or not

    def __str__(self):
        return f"License {self.license_id} for Device {self.device_id} ({'Active' if self.isActive else 'Inactive'})"

    class Meta:
        verbose_name = "License"
        verbose_name_plural = "Licenses"
