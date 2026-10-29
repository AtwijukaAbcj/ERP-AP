from rest_framework import viewsets
from .models import User, Role, Permission
from .serializers import UserSerializer, RoleSerializer, PermissionSerializer
from .permissions import IsSuperAdministrator


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsSuperAdministrator]


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all().order_by("name")
    serializer_class = RoleSerializer
    permission_classes = [IsSuperAdministrator]


class PermissionViewSet(viewsets.ModelViewSet):
    queryset = Permission.objects.all().order_by("code")
    serializer_class = PermissionSerializer
    permission_classes = [IsSuperAdministrator]
