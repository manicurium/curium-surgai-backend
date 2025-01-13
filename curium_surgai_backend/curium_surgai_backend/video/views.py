from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .serializers import VideoSerializer


class VideoCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new video entry",
        request_body=VideoSerializer,
        responses={
            201: openapi.Response(
                description="Video created successfully", schema=VideoSerializer
            ),
            400: "Bad Request",
            401: "Unauthorized",
        },
    )
    def post(self, request):
        context = {"request": request}
        serializer = VideoSerializer(data=request.data, context=context)

        if serializer.is_valid():

            # Automatically set the uploaded_by field to current user
            _ = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
