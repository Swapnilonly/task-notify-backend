import time

class RequestLoggerMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        print(f"Request Method: {request.method}")
        print(f"Request Path: {request.path}")

        response = self.get_response(request)

        duration = time.time() - start_time
        print(f"Response Time: {duration:.4f} sec")

        return response

# ✅ 8️⃣ middleware/
#
# Use it for:
#
# Logging
#
# Request tracking
#
# Performance monitoring
#
# Global error formatting