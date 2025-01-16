from django.contrib import admin
from django.urls import path, include
from swagger.views import schema_view


urlpatterns = [
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("admin/", admin.site.urls),
    # REST framework
    path("api/", include("video.urls")),
    path("api/", include("frame.urls")),
    # path("api/", include("license.urls")),
    path("api/", include("report.urls")),
    path("api/", include("user.urls")),
    path("api/", include("device.urls")),
]
