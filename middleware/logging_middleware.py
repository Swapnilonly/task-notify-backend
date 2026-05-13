"""
middleware/logging_middleware.py

Logs every HTTP request:
  method · path · query_params · user · user_id · status_code
  duration_ms · ip · user_agent

Uses logger "app" → goes to logs_dir/app.log (JSON) + console.
Skip paths (health, static) are configurable via settings.LOGGING_SKIP_PATHS.
"""

import logging
import time

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("app")

DEFAULT_SKIP_PATHS = {"/health/", "/ping/", "/static/", "/media/", "/favicon.ico"}


class RequestLoggingMiddleware(MiddlewareMixin):

    skip_paths: set = getattr(settings, "LOGGING_SKIP_PATHS", DEFAULT_SKIP_PATHS)

    def process_request(self, request):
        request._log_start = time.monotonic()

    def process_response(self, request, response):
        for skip in self.skip_paths:
            if request.path.startswith(skip):
                return response

        duration_ms = round(
            (time.monotonic() - getattr(request, "_log_start", time.monotonic())) * 1000, 2
        )

        user = getattr(request, "user", None)
        is_auth = user and getattr(user, "is_authenticated", False)

        extra = {
            "method":       request.method,
            "path":         request.path,
            "query_params": request.META.get("QUERY_STRING") or None,
            "user":         getattr(user, "email", "anonymous") if is_auth else "anonymous",
            "user_id":      str(getattr(user, "pk", "")) if is_auth else None,
            "status_code":  response.status_code,
            "duration_ms":  duration_ms,
            "ip":           self._get_ip(request),
            "user_agent":   request.META.get("HTTP_USER_AGENT", "")[:200],
        }

        if response.status_code >= 500:
            logger.error("request", extra=extra)
        elif response.status_code >= 400:
            logger.warning("request", extra=extra)
        else:
            logger.info("request", extra=extra)

        return response

    @staticmethod
    def _get_ip(request) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")