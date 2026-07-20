from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

class JWTCookieAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # 1. Try to authenticate using standard Header Bearer token first (great for APIs/Postman)
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
        else:
            # 2. If no header, fallback to the HttpOnly cookie
            raw_token = request.COOKIES.get('access_token')

        if raw_token is None:
            return None

        try:
            # Validate the token
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token
        except (InvalidToken, TokenError):
            # Return None to allow DRF permission checks to decide authorization.
            # This avoids breaking AllowAny endpoints when invalid or expired tokens are present.
            return None
