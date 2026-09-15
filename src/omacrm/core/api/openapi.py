from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from omacrm.core.services.openapi import build_spec


class OpenApiView(APIView):
    """Serve the metadata-driven OpenAPI document for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_spec(request.user))
