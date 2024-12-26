from django.contrib import admin
from django.urls import path, include
from .swagger.views import schema_view


urlpatterns = [
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("admin/", admin.site.urls),
    # REST framework
    path("api/", include("curium_surgai_backend.video.urls")),
    path("api/", include("curium_surgai_backend.frame.urls")),
    path("api/", include("curium_surgai_backend.user.urls")),
    path("api/", include("curium_surgai_backend.license.urls")),
    path("api/", include("curium_surgai_backend.report.urls")),
]
