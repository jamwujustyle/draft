from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        
        # We set username to email if it is not provided, since Django's AbstractUser has username unique=True.
        # Although we set USERNAME_FIELD = 'email', keeping username field synchronized or blank is helpful.
        username = extra_fields.get('username', email)
        extra_fields['username'] = username
        
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'client')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    class Role(models.TextChoices):
        ADVERTISER = 'advertiser', 'Advertiser/Promoter'
        CLIENT = 'client', 'Client'

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20, 
        choices=Role.choices, 
        default=Role.CLIENT
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"

class OTPToken(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    role = models.CharField(
        max_length=20,
        choices=User.Role.choices,
        default=User.Role.CLIENT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"OTP for {self.email} - {self.code} ({'Used' if self.is_used else 'Active'})"
