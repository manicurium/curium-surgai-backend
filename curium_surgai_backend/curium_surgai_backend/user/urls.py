from django.urls import path
from .views import registration_view, get_users
from rest_framework_simplejwt import views as jwt_views

urlpatterns = [
    path("user/register", registration_view, name="register"),
    path("auth/token", jwt_views.TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh", jwt_views.TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/revoke", jwt_views.TokenBlacklistView.as_view(), name="auth_logout"),
    path("user", get_users, name="users"),
]
