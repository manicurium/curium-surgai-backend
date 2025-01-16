import random
import string
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import jwt
from rest_framework_simplejwt.tokens import RefreshToken


def generate_otp():
    # return "".join(random.choices(string.digits, k=4))
    return "1234"


def send_otp_to_user(email, otp):
    try:
        subject = "Your OTP for Authentication"
        message = f"Your OTP is: {otp}. This OTP will expire in 10 minutes."
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [email]

        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False


def generate_jwt_token(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
