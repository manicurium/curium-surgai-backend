from rest_framework import serializers
from .models import Report

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['report_id', 'video_id', 'report_date', 'report_json']
        read_only_fields = ['report_id', 'report_date']  # Make the report_id and report_date read-only
