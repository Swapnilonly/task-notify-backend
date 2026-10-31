from rest_framework.throttling import AnonRateThrottle

class RegisterRateThrottle(AnonRateThrottle):
    """Limit signups per IP so the endpoint can't be used for spam accounts."""

    scope = "register"