from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("report_id", "video", "report_date", "score")
        read_only_fields = ("report_id", "report_date")

    def __init__(self, *args, **kwargs):
        # Extract report_json from context
        report_json = kwargs.pop("context", {}).get("report_json", False)
        super().__init__(*args, **kwargs)

        # Include report_json field if requested
        if report_json:
            self.fields["report_json"] = serializers.JSONField(read_only=True)

    def save(self):
        video = self.validated_data.get("video", None)
        report_json = self.validated_data.get("report_json", None)
        score = self.validated_data.get("score", {})
        report = Report(report_json=report_json, video=video, score=score)
        report.save()
        return report
