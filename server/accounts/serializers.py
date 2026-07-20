from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
        read_only_fields = ('id', 'is_active', 'date_joined')

class PasswordlessRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordlessVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)

class GoogleAuthSerializer(serializers.Serializer):
    credential = serializers.CharField(help_text="Google JWT ID Token from the front-end")
