from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from .models import License
from .serializers import LicenseSerializer

# License creation view - user can create a new license
@swagger_auto_schema(
    method="post",
    request_body=LicenseSerializer,
    responses={201: LicenseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can create licenses
def create_license(request):
    if request.method == "POST":
        serializer = LicenseSerializer(data=request.data)

        # Ensure the data is valid
        if serializer.is_valid():
            serializer.save()  # Save the license
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# License list view - user can get a list of all licenses
@swagger_auto_schema(
    method="get",
    responses={200: LicenseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Ensure only authenticated users can view licenses
def get_licenses(request):
    licenses = License.objects.all()  # Retrieve all licenses

    # Serialize the licenses and return them
    serializer = LicenseSerializer(licenses, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

# License detail view - user can get details for a specific license by license_id
@swagger_auto_schema(
    method="get",
    responses={200: LicenseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_license_detail(request, license_id):
    try:
        license = License.objects.get(license_id=license_id)  # Retrieve license by UUID
    except License.DoesNotExist:
        return Response({"detail": "License not found."}, status=status.HTTP_404_NOT_FOUND)

    # Serialize and return the license details
    serializer = LicenseSerializer(license)
    return Response(serializer.data, status=status.HTTP_200_OK)
