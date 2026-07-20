from django.urls import path
from .views import (
    PasswordlessRequestView,
    PasswordlessVerifyView,
    GoogleAuthView,
    CookieTokenRefreshView,
    LogoutView,
    MeView
)

urlpatterns = [
    path('passwordless/request/', PasswordlessRequestView.as_view(), name='passwordless-request'),
    path('passwordless/verify/', PasswordlessVerifyView.as_view(), name='passwordless-verify'),
    path('google/', GoogleAuthView.as_view(), name='google-auth'),
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token-refresh'),
]
