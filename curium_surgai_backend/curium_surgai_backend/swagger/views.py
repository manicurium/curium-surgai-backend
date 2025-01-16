from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Curium",
        default_version="v1",
        description="Curium Surgai Backend management API",
    ),
    public=True,
    permission_classes=(
        permissions.AllowAny,
    ),  # You can set this to a more restricted permission if needed
)
