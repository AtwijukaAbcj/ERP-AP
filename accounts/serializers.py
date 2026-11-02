from rest_framework import serializers
from .models import User, Role, Permission


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "slug", "description"]


class PermissionSerializer(serializers.ModelSerializer):
    codename = serializers.CharField(source="code")

    class Meta:
        model = Permission
        fields = ["id", "name", "codename", "description"]


class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "roles",
            "is_staff",
            "is_superuser",
        ]
        read_only_fields = ["id", "is_staff", "is_superuser"]
