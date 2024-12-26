from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from curium_surgai_backend.video.models import Video  # Import Video model
from curium_surgai_backend.video.serializers import VideoSerializer  # Import Video serializer


# Video creation view - user uploads a new video
@swagger_auto_schema(
    method="post",
    request_body=VideoSerializer,
    responses={201: VideoSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can upload videos
def upload_video(request):
    if request.method == "POST":
        serializer = VideoSerializer(data=request.data)

        # Ensure the 'uploaded_by' field is automatically populated with the current user
        if serializer.is_valid():
            # Save the video with the current authenticated user
            serializer.save(uploaded_by=request.user)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Video list or detail view - user can get video details or a list of videos
@swagger_auto_schema(
    method="get",
    responses={200: VideoSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can view videos
def get_videos(request):
    # If the user wants to filter based on some parameters (e.g., only videos they uploaded)
    user = request.user
    videos = Video.objects.filter(uploaded_by=user)  # Filter videos uploaded by the current user

    # Serializer the videos
    serializer = VideoSerializer(videos, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Video detail view - user can get details for a specific video by video_id
@swagger_auto_schema(
    method="get",
    responses={200: VideoSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_video_detail(request, video_id):
    try:
        video = Video.objects.get(video_id=video_id)  # Fetch the video by UUID
    except Video.DoesNotExist:
        return Response({"detail": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

    # Serialize and return the video details
    serializer = VideoSerializer(video)
    return Response(serializer.data, status=status.HTTP_200_OK)