from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPToken

User = get_user_model()

@override_settings(DEBUG=True)
class AuthTests(APITestCase):

    def setUp(self):
        self.request_otp_url = reverse('passwordless-request')
        self.verify_otp_url = reverse('passwordless-verify')
        self.google_auth_url = reverse('google-auth')
        self.me_url = reverse('me')
        self.logout_url = reverse('logout')
        self.refresh_url = reverse('token-refresh')

    def test_passwordless_request_flow(self):
        # Request OTP — no role field anymore
        data = {"email": "promoter_test@example.com"}
        response = self.client.post(self.request_otp_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("code", response.data)

        # OTPToken is created with client as default role
        otp_token = OTPToken.objects.filter(email="promoter_test@example.com").first()
        self.assertIsNotNone(otp_token)
        self.assertFalse(otp_token.is_used)

    def test_passwordless_verify_success_sets_httponly_cookies(self):
        # Request code
        req_response = self.client.post(self.request_otp_url, {
            "email": "new_client@example.com"
        })
        code = req_response.data["code"]

        # Verify code
        verify_response = self.client.post(self.verify_otp_url, {
            "email": "new_client@example.com",
            "code": code
        })
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        # Tokens are NOT in JSON payload
        self.assertNotIn("access", verify_response.data)
        self.assertNotIn("refresh", verify_response.data)
        self.assertEqual(verify_response.data["user"]["email"], "new_client@example.com")

        # HttpOnly cookies are set
        self.assertIn("access_token", verify_response.cookies)
        self.assertIn("refresh_token", verify_response.cookies)
        self.assertTrue(verify_response.cookies["access_token"]["httponly"])
        self.assertTrue(verify_response.cookies["refresh_token"]["httponly"])

    def test_google_auth_mock_sets_httponly_cookies(self):
        # No role field — Google users always register as client
        data = {"credential": "mock_google_token_google_user@example.com"}
        response = self.client.post(self.google_auth_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])
        self.assertEqual(response.data["user"]["email"], "google_user@example.com")

    def test_me_endpoint_authenticates_via_cookie(self):
        user = User.objects.create_user(email="user_me@example.com")
        refresh = RefreshToken.for_user(user)
        self.client.cookies['access_token'] = str(refresh.access_token)

        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["email"], "user_me@example.com")

    def test_token_refresh_via_cookie(self):
        user = User.objects.create_user(email="user_refresh@example.com")
        refresh = RefreshToken.for_user(user)
        self.client.cookies['refresh_token'] = str(refresh)

        response = self.client.post(self.refresh_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

    def test_logout_clears_cookies(self):
        self.client.cookies['access_token'] = 'some_access_token'
        self.client.cookies['refresh_token'] = 'some_refresh_token'

        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies['access_token'].value, '')
        self.assertEqual(response.cookies['refresh_token'].value, '')
