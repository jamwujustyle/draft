import random
import logging
import requests
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import OTPToken
from .serializers import (
    UserSerializer,
    PasswordlessRequestSerializer,
    PasswordlessVerifySerializer,
    GoogleAuthSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    # Add custom claims to standard payload
    refresh['email'] = user.email
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

def set_auth_cookies(response, tokens):
    simple_jwt_settings = getattr(settings, 'SIMPLE_JWT', {})
    access_lifetime = simple_jwt_settings.get('ACCESS_TOKEN_LIFETIME', timedelta(days=1))
    refresh_lifetime = simple_jwt_settings.get('REFRESH_TOKEN_LIFETIME', timedelta(days=7))

    # Set access token in HttpOnly cookie
    response.set_cookie(
        key='access_token',
        value=tokens['access'],
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS only in production
        samesite='Lax',
        max_age=int(access_lifetime.total_seconds())
    )

    # Set refresh token in HttpOnly cookie
    response.set_cookie(
        key='refresh_token',
        value=tokens['refresh'],
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS only in production
        samesite='Lax',
        max_age=int(refresh_lifetime.total_seconds())
    )

class PasswordlessRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordlessRequestSerializer,
        responses={200: OpenApiResponse(description='OTP code sent (code returned in DEBUG mode)')},
        summary='Request passwordless OTP',
        tags=['auth'],
    )
    def post(self, request, *args, **kwargs):
        serializer = PasswordlessRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']

        # Generate a 6-digit verification code
        code = f"{random.randint(100000, 999999)}"
        expires_at = timezone.now() + timedelta(minutes=10)

        # Create the OTP Token record — role always defaults to client
        OTPToken.objects.create(
            email=email,
            code=code,
            expires_at=expires_at
        )

        # Send mail via configured Django backend
        subject = "Your Login Verification Code"
        message = f"Your verification code is: {code}\nThis code expires in 10 minutes."

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {e}")
            if not settings.DEBUG:
                return Response(
                    {"error": "Failed to send verification email. Please try again later."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        response_data = {"message": "Verification code has been sent."}
        # In debug mode, return the code so developers can quickly test
        if settings.DEBUG:
            response_data["code"] = code

        return Response(response_data, status=status.HTTP_200_OK)

class PasswordlessVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=PasswordlessVerifySerializer,
        responses={200: UserSerializer},
        summary='Verify OTP and authenticate',
        tags=['auth'],
    )
    def post(self, request, *args, **kwargs):
        serializer = PasswordlessVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        # Find the latest unexpired valid token for this email and code
        otp_token = OTPToken.objects.filter(
            email=email,
            code=code,
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

        if not otp_token:
            return Response(
                {"error": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark the token as used
        otp_token.is_used = True
        otp_token.save()

        # Check if the user exists, otherwise create
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': '',
                'last_name': ''
            }
        )

        tokens = get_tokens_for_user(user)
        response = Response({
            "user": UserSerializer(user).data,
            "is_new_user": created
        }, status=status.HTTP_200_OK)

        # Set tokens in HttpOnly cookies
        set_auth_cookies(response, tokens)
        return response

class GoogleAuthView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=GoogleAuthSerializer,
        responses={200: UserSerializer},
        summary='Google OAuth2 sign-in / sign-up',
        tags=['auth'],
    )
    def post(self, request, *args, **kwargs):
        serializer = GoogleAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        credential = serializer.validated_data['credential']

        email = None
        first_name = ""
        last_name = ""

        # Check for mock token if in debug mode to ease testing
        if settings.DEBUG and credential.startswith("mock_google_token_"):
            email = credential.replace("mock_google_token_", "")
            first_name = "GoogleMock"
            last_name = "User"
        else:
            # Verify the credential (ID Token) directly with Google's API
            google_verify_url = "https://oauth2.googleapis.com/tokeninfo"
            try:
                response = requests.get(google_verify_url, params={"id_token": credential}, timeout=10)
                if response.status_code != 200:
                    return Response(
                        {"error": "Invalid Google credential."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                payload = response.json()

                # Verify audience to prevent token reuse across other apps
                aud = payload.get("aud")
                if settings.GOOGLE_CLIENT_ID and aud != settings.GOOGLE_CLIENT_ID:
                    return Response(
                        {"error": "Token was not issued for this application."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                email = payload.get("email")
                first_name = payload.get("given_name", "")
                last_name = payload.get("family_name", "")

                if not email:
                    return Response(
                        {"error": "Email not provided by Google account."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            except requests.RequestException as e:
                logger.error(f"Google verification network error: {e}")
                return Response(
                    {"error": "Could not connect to Google verification services."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

        # Get or create the user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name
            }
        )

        tokens = get_tokens_for_user(user)
        response = Response({
            "user": UserSerializer(user).data,
            "is_new_user": created
        }, status=status.HTTP_200_OK)

        # Set tokens in HttpOnly cookies
        set_auth_cookies(response, tokens)
        return response

class CookieTokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=None,
        responses={200: UserSerializer},
        summary='Refresh JWT tokens from cookie',
        tags=['auth'],
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response(
                {"error": "Refresh token not found in cookies."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validate refresh token and load user
            token = RefreshToken(refresh_token)
            user_id = token.payload.get('user_id')
            user = User.objects.get(id=user_id)

            # Generate new rotated tokens
            tokens = get_tokens_for_user(user)

            response = Response({
                "user": UserSerializer(user).data
            }, status=status.HTTP_200_OK)

            # Set new cookies
            set_auth_cookies(response, tokens)
            return response

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return Response(
                {"error": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED
            )

class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description='Successfully logged out')},
        summary='Logout and clear cookies',
        tags=['auth'],
    )
    def post(self, request, *args, **kwargs):
        response = Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response

class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: UserSerializer},
        summary='Get current authenticated user',
        tags=['auth'],
    )
    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response({"user": serializer.data}, status=status.HTTP_200_OK)
