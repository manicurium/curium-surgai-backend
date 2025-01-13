from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Device
from drf_yasg.utils import swagger_auto_schema
from .serializers import DeviceSerializer
from drf_yasg import openapi
from rest_framework_simplejwt.authentication import JWTAuthentication


@swagger_auto_schema(
    method="post",
    operation_description="Start streaming for a specific device",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["mac_address"],
        properties={
            "mac_address": openapi.Schema(
                type=openapi.TYPE_STRING, description="MAC address of the device"
            )
        },
    ),
    responses={
        200: openapi.Response(
            description="Stream started successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "mqtt_topic": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="MQTT topic for the device",
                    )
                },
            ),
        ),
        404: openapi.Response(
            description="Device not found",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "error": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Error message"
                    )
                },
            ),
        ),
        401: "Unauthorized",
    },
    tags=["Devices"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_stream(request):
    device_id = request.data.get("mac_address")
    try:
        device = Device.objects.get(mac_address=device_id)
        return Response({"mqtt_topic": device.mqtt_topic})
    except Device.DoesNotExist:
        return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)


class DeviceCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Register a new device",
        request_body=DeviceSerializer,
        responses={
            201: openapi.Response(
                description="Device registered successfully", schema=DeviceSerializer
            ),
            400: openapi.Response(
                description="Bad Request",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "error": openapi.Schema(
                            type=openapi.TYPE_STRING, description="Error message"
                        )
                    },
                ),
            ),
            401: "Unauthorized",
        },
        tags=["Devices"],
    )
    def post(self, request):
        context = {"request": request}
        serializer = DeviceSerializer(data=request.data, context=context)

        if serializer.is_valid():
            _ = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="get",
    operation_description="Get device details using MAC address",
    manual_parameters=[
        openapi.Parameter(
            "mac_address",
            openapi.IN_QUERY,
            description="MAC address of the device",
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    responses={
        200: DeviceSerializer,
        404: openapi.Response(
            description="Device not found",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "error": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Error message"
                    )
                },
            ),
        ),
        400: openapi.Response(
            description="Invalid MAC address format",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "error": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Error message"
                    )
                },
            ),
        ),
        401: "Unauthorized",
    },
    tags=["Devices"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_device_details(request):
    mac_address = request.query_params.get("mac_address")

    if not mac_address:
        return Response(
            {"error": "MAC address is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    # Optional: Add MAC address format validation
    import re

    mac_pattern = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")
    if not mac_pattern.match(mac_address):
        return Response(
            {"error": "Invalid MAC address format. Use format XX:XX:XX:XX:XX:XX"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        device = Device.objects.get(mac_address=mac_address)
        serializer = DeviceSerializer(device)
        return Response(serializer.data)
    except Device.DoesNotExist:
        return Response(
            {"error": "Device not found or you don't have permission to access it"},
            status=status.HTTP_404_NOT_FOUND,
        )
