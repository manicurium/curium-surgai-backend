from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from curium_surgai_backend.user.serializers import (
    RegistrationSerializer,
    ProfileSerializer,
    ProfilesSerializer,
)
from drf_yasg.utils import swagger_auto_schema
from .models import User


@swagger_auto_schema(
    method="post",
    request_body=RegistrationSerializer,
    responses={201: RegistrationSerializer},
)
@api_view(["POST"])
@permission_classes([AllowAny])
def registration_view(request):
    if request.method == "POST":
        serializer = RegistrationSerializer(data=request.data)
        data = {}
        if serializer.is_valid():
            user = serializer.save()

            data["email"] = user.email_id
            data["lname"] = user.lname
            data["fname"] = user.fname
            data["id"] = user.id
            data["role_type"] = user.role_type  # Return role_type in response
            return Response(data, status=status.HTTP_201_CREATED)
        else:
            data = serializer.errors
            return Response(data, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="get",
    responses={200: ProfileSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_users(request):

    queryset = User.objects.all()

    serializer = ProfilesSerializer(queryset, many=True)
    return Response(serializer.data)
