from django.urls import path

from .views import LoginSignupView, VerifyOTPView

from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Authentication API",
        default_version="v1",
        description="API for user authentication with email and OTP",
        terms_of_service="https://www.yourapp.com/terms/",
        contact=openapi.Contact(email="contact@yourapp.com"),
        license=openapi.License(name="Your License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
urlpatterns = [
    path("auth/login", LoginSignupView.as_view(), name="login-signup"),
    path("auth/verify", VerifyOTPView.as_view(), name="verify-otp"),
]
