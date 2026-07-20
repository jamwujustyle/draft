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
        # 1. Request OTP for advertiser
        data = {
            "email": "promoter_test@example.com",
            "role": "advertiser"
        }
        response = self.client.post(self.request_otp_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("code", response.data)  # Returned in response during settings.DEBUG=True

        # Verify OTPToken is created
        otp_token = OTPToken.objects.filter(email="promoter_test@example.com").first()
        self.assertIsNotNone(otp_token)
        self.assertEqual(otp_token.role, "advertiser")
        self.assertFalse(otp_token.is_used)

    def test_passwordless_verify_success_sets_httponly_cookies(self):
        # 1. Request code
        req_response = self.client.post(self.request_otp_url, {
            "email": "new_client@example.com",
            "role": "client"
        })
        code = req_response.data["code"]

        # 2. Verify code
        verify_response = self.client.post(self.verify_otp_url, {
            "email": "new_client@example.com",
            "code": code
        })
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        
        # Verify tokens are NOT returned in JSON payload directly
        self.assertNotIn("access", verify_response.data)
        self.assertNotIn("refresh", verify_response.data)
        self.assertEqual(verify_response.data["user"]["email"], "new_client@example.com")
        self.assertEqual(verify_response.data["user"]["role"], "client")

        # Verify HttpOnly cookies are set
        self.assertIn("access_token", verify_response.cookies)
        self.assertIn("refresh_token", verify_response.cookies)
        self.assertTrue(verify_response.cookies["access_token"]["httponly"])
        self.assertTrue(verify_response.cookies["refresh_token"]["httponly"])

    def test_google_auth_mock_sets_httponly_cookies(self):
        # Use mock token to register as advertiser
        data = {
            "credential": "mock_google_token_google_adv@example.com",
            "role": "advertiser"
        }
        response = self.client.post(self.google_auth_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])
        self.assertEqual(response.data["user"]["email"], "google_adv@example.com")
        self.assertEqual(response.data["user"]["role"], "advertiser")

    def test_me_endpoint_authenticates_via_cookie(self):
        # Create user
        user = User.objects.create_user(email="user_me@example.com", role="client")
        refresh = RefreshToken.for_user(user)
        
        # Set access token in cookie for the client
        self.client.cookies['access_token'] = str(refresh.access_token)
        
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["email"], "user_me@example.com")

    def test_token_refresh_via_cookie(self):
        # Create user and active refresh token
        user = User.objects.create_user(email="user_refresh@example.com", role="client")
        refresh = RefreshToken.for_user(user)
        
        # Set refresh token in cookie
        self.client.cookies['refresh_token'] = str(refresh)
        
        response = self.client.post(self.refresh_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify new rotated cookies are set
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)

    def test_logout_clears_cookies(self):
        # Log in first or mock setting cookies
        self.client.cookies['access_token'] = 'some_access_token'
        self.client.cookies['refresh_token'] = 'some_refresh_token'
        
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify cookies are cleared (max-age=0 or empty value)
        self.assertEqual(response.cookies['access_token'].value, '')
        self.assertEqual(response.cookies['refresh_token'].value, '')
