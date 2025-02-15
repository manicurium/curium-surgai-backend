from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("report_id", "video", "report_date", "report_json", "score")
        read_only_fields = ("report_id", "report_date")

    def save(self):
        video = self.validated_data.get("video", None)
        report_json = self.validated_data.get("report_json", None)
        score = self.validated_data.get("score", {})
        report = Report(report_json=report_json, video=video, score=score)
        report.save()
        return report
