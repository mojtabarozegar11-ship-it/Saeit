from django.conf import settings
from django.db import connection
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.status import HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.views import APIView


def home(request):
    return render(
        request,
        "core/home.html",
        {
            "app_version": getattr(settings, "APP_VERSION", "0.1.0"),
        },
    )


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            return Response(
                {
                    "status": "degraded",
                    "service": "saeit",
                    "database": "unavailable",
                    "error": exc.__class__.__name__,
                },
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "status": "ok",
                "service": "saeit",
                "version": getattr(settings, "APP_VERSION", "0.1.0"),
                "database": "ok",
            }
        )
