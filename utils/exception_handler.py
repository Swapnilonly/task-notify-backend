"""
utils/exception_handler.py
Wraps DRF's default handler to add consistent JSON structure + logging.
All error responses follow: {"error": "...", "detail": ...}
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("app")


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    request = context.get("request")
    view    = context.get("view")

    extra = {
        "exception":   exc.__class__.__name__,
        "view":        view.__class__.__name__ if view else "unknown",
        "path":        getattr(request, "path", ""),
        "user":        str(getattr(getattr(request, "user", None), "pk", "anonymous")),
    }

    if response is not None:
        if response.status_code >= 500:
            logger.error("handled_exception", extra={**extra, "detail": str(exc)}, exc_info=True)
        elif response.status_code >= 400:
            logger.warning("client_error", extra={**extra, "status": response.status_code})

        response.data = {
            "error":  exc.__class__.__name__,
            "detail": response.data,
        }
    else:
        # Unhandled exception — return 500
        logger.error("unhandled_exception", extra=extra, exc_info=True)
        response = Response(
            {"error": "InternalServerError", "detail": "An unexpected error occurred."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response