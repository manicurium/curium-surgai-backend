from rest_framework import serializers
from .models import License

class LicenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = License
        fields = ['license_id', 'org_code', 'device_id', 'device_MAC', 'created_at', 'isActive']
        read_only_fields = ['license_id', 'created_at']  # Read-only fields
