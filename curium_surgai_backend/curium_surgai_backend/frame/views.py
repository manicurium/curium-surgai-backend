from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .models import Video
from .serializers import ProcessedFrameSerializer


class ProcessedFrameCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a processed frame entry for a video",
        request_body=ProcessedFrameSerializer,
        responses={
            201: openapi.Response(
                description="Frame processed successfully",
                schema=ProcessedFrameSerializer,
            ),
            400: "Bad Request",
            401: "Unauthorized",
            404: "Video not found",
        },
    )
    def post(self, request):
        # Add video validation to ensure user owns the video
        video_id = request.data.get("video")
        if video_id:
            video = get_object_or_404(Video, video_id=video_id)
            if video.uploaded_by != request.user:
                return Response(
                    {"error": "You don't have permission to add frames to this video"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = ProcessedFrameSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
