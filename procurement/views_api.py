from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import SupplierCategory, Supplier, ProcurementPlan, PurchaseRequisition, PurchaseOrder
from .serializers import (
    SupplierCategorySerializer,
    SupplierSerializer,
    ProcurementPlanSerializer,
    PurchaseRequisitionSerializer,
    PurchaseOrderSerializer,
)
from accounts.permissions import IsProcurementOfficer, IsProcurementManager


class SupplierCategoryViewSet(viewsets.ModelViewSet):
    queryset = SupplierCategory.objects.filter(deleted_at__isnull=True).order_by("name")
    serializer_class = SupplierCategorySerializer
    permission_classes = [IsAuthenticated, IsProcurementManager]


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.filter(deleted_at__isnull=True).order_by("name")
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, IsProcurementOfficer]


class ProcurementPlanViewSet(viewsets.ModelViewSet):
    queryset = ProcurementPlan.objects.filter(deleted_at__isnull=True).order_by("created_at")
    serializer_class = ProcurementPlanSerializer
    permission_classes = [IsAuthenticated, IsProcurementOfficer]


class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    queryset = PurchaseRequisition.objects.filter(deleted_at__isnull=True).order_by("created_at")
    serializer_class = PurchaseRequisitionSerializer
    permission_classes = [IsAuthenticated, IsProcurementOfficer]


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.filter(deleted_at__isnull=True).order_by("created_at")
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated, IsProcurementManager]
