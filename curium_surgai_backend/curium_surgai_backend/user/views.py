from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
from rest_framework.permissions import AllowAny
from .models import User, OTPRecord
from .serializers import (
    UserSerializer,
    OTPVerificationSerializer,
    LoginSignupSerializer,
)
from .utils import generate_otp, send_otp_to_user, generate_jwt_token
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.utils import timezone


class LoginSignupView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Login or Signup using email with OTP verification",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL
                ),
                "username": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Optional username. If not provided, will use part before @ in email",
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="OTP sent successfully",
                examples={
                    "application/json": {
                        "message": "OTP sent successfully",
                        "user_exists": True,
                    }
                },
            ),
            400: openapi.Response(
                description="Bad request",
                examples={
                    "application/json": {"email": ["Enter a valid email address."]}
                },
            ),
        },
    )
    def post(self, request):
        serializer = LoginSignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()

        # Generate and send OTP
        otp = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)

        OTPRecord.objects.create(email=email, otp=otp, expires_at=expires_at)

        if not user:
            username = serializer.validated_data.get("username")
            if not username:
                username = email
            user = User.objects.create(username=username, email=email)

        # Send OTP and handle failure
        if not send_otp_to_user(email, otp):
            return Response(
                {"message": "Failed to send OTP. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"message": "OTP sent successfully", "user_exists": user is not None}
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Verify OTP and get authentication tokens",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "otp"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description="Email address to verify",
                ),
                "otp": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="4-digit OTP code sent to email",
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="OTP verified successfully",
                examples={
                    "application/json": {
                        "message": "OTP verified successfully",
                        "tokens": {
                            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                            "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                        },
                    }
                },
            ),
            400: openapi.Response(
                description="Bad request",
                examples={"application/json": {"message": "Invalid OTP"}},
            ),
            404: openapi.Response(description="User not found"),
        },
    )
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        otp_record = (
            OTPRecord.objects.filter(email=email, expires_at__gt=timezone.now())
            .order_by("-created_at")
            .first()
        )

        if not otp_record:
            return Response(
                {"message": "OTP expired or not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_record.attempts >= 3:
            return Response(
                {"message": "Maximum attempts exceeded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_record.otp != otp:
            otp_record.attempts += 1
            otp_record.save()
            return Response(
                {"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = get_object_or_404(User, email=email)
        user.is_email_verified = True
        user.save()

        tokens = generate_jwt_token(user)
        return Response({"message": "OTP verified successfully", "tokens": tokens})
