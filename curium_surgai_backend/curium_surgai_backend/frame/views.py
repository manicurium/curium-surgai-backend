from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from curium_surgai_backend.frame.models import Frame  # Import Frame model
from curium_surgai_backend.frame.serializers import FrameSerializer  # Import Frame serializer


# Frame creation view - user uploads a new frame
@swagger_auto_schema(
    method="post",
    request_body=FrameSerializer,
    responses={201: FrameSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can upload frames
def upload_frame(request):
    if request.method == "POST":
        serializer = FrameSerializer(data=request.data)

        # Ensure the 'video_id' field is populated correctly and valid
        if serializer.is_valid():
            # Optionally, you can assign the frame to the current video based on the incoming data
            # Assuming you pass a 'video_id' with the frame data
            serializer.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Frame list view - user can get a list of frames associated with their videos
@swagger_auto_schema(
    method="get",
    responses={200: FrameSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can view frames
def get_frames(request):
    # Get all frames associated with the current authenticated user's videos
    user = request.user
    frames = Frame.objects.filter(video_id__uploaded_by=user)  # Filter frames by video uploader

    # Serialize the frames
    serializer = FrameSerializer(frames, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Frame detail view - user can get details for a specific frame by processed_frame_id
@swagger_auto_schema(
    method="get",
    responses={200: FrameSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can view frame details
def get_frame_detail(request, processed_frame_id):
    try:
        frame = Frame.objects.get(processed_frame_id=processed_frame_id)  # Fetch frame by UUID
    except Frame.DoesNotExist:
        return Response({"detail": "Frame not found."}, status=status.HTTP_404_NOT_FOUND)

    # Serialize and return the frame details
    serializer = FrameSerializer(frame)
    return Response(serializer.data, status=status.HTTP_200_OK)
