from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers
from django.utils import timezone

from .models import (
    PurchaseOrderItem,
    SupplierCategory,
    Supplier,
    ProcurementPlan,
    PurchaseRequisition,
    PurchaseOrder,
    PurchaseQuotation,
)


class SupplierCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierCategory
        fields = ["id", "name", "description"]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "category", "email", "phone", "address", "is_blacklisted", "created_by"]
        read_only_fields = ["created_by"]


class ProcurementPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcurementPlan
        fields = ["id", "title", "department", "fiscal_year", "requested_by", "approved", "approved_at"]
        read_only_fields = ["requested_by", "approved", "approved_at"]

    def create(self, validated_data):
        validated_data["requested_by"] = self.context["request"].user
        return super().create(validated_data)


class PurchaseRequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseRequisition
        fields = [
            "id",
            "title",
            "description",
            "department",
            "requested_by",
            "status",
            "total_amount",
            "required_by",
            "attachments",
        ]
        read_only_fields = ["requested_by", "status"]

    def create(self, validated_data):
        from .models import ProcurementStatus, PurchaseRequisitionStatusHistory

        validated_data["requested_by"] = self.context["request"].user
        validated_data["status"], _ = ProcurementStatus.objects.get_or_create(
            slug="draft",
            defaults={"name": "Draft", "is_default": True},
        )
        requisition = super().create(validated_data)
        PurchaseRequisitionStatusHistory.objects.create(
            requisition=requisition,
            to_status="draft",
            comment="Requisition created through the API.",
            changed_by=self.context["request"].user,
        )
        return requisition


class PurchaseOrderSerializer(serializers.ModelSerializer):
    quotation = serializers.PrimaryKeyRelatedField(
        queryset=PurchaseQuotation.objects.filter(
            deleted_at__isnull=True,
            status=PurchaseQuotation.Status.ACCEPTED,
            requisition__deleted_at__isnull=True,
            requisition__status__slug="approved",
            purchase_orders__isnull=True,
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.localdate()),
            document__gt="",
        )
    )
    supplier = serializers.PrimaryKeyRelatedField(read_only=True)
    requisition = serializers.PrimaryKeyRelatedField(read_only=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        allow_empty=False,
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "supplier",
            "requisition",
            "quotation",
            "items",
            "order_date",
            "total_amount",
            "approved",
            "approved_at",
        ]
        read_only_fields = ["order_date", "total_amount", "approved", "approved_at"]

    def validate_items(self, items):
        validated_items = []
        for item in items:
            try:
                description = item["description"]
                quantity = int(item["quantity"])
                unit_price = Decimal(str(item["unit_price"]))
            except (KeyError, TypeError, ValueError, ArithmeticError) as error:
                raise serializers.ValidationError(
                    "Each item requires a description, positive quantity, and positive unit price."
                ) from error
            if not description or quantity < 1 or not unit_price.is_finite() or unit_price <= 0:
                raise serializers.ValidationError(
                    "Each item requires a description, positive quantity, and positive unit price."
                )
            validated_items.append(
                {
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                }
            )
        return validated_items

    def validate_quotation(self, quotation):
        if quotation.supplier.is_blacklisted or quotation.supplier.deleted_at is not None:
            raise serializers.ValidationError(
                "Blacklisted or inactive suppliers cannot receive purchase orders."
            )
        if quotation.requisition.total_amount > 0 and quotation.total_amount > quotation.requisition.total_amount:
            raise serializers.ValidationError(
                "The accepted quotation exceeds the approved requisition amount."
            )
        if not quotation.items.exists() or quotation.items_total != quotation.total_amount:
            raise serializers.ValidationError(
                "The accepted quotation has incomplete or inconsistent line items."
            )
        if quotation.valid_until and quotation.valid_until < timezone.localdate():
            raise serializers.ValidationError("The accepted supplier quotation has expired.")
        if quotation.purchase_orders.exclude(
            pk=getattr(self.instance, "pk", None)
        ).filter(deleted_at__isnull=True).exists():
            raise serializers.ValidationError(
                "A purchase order already exists for this quotation."
            )
        return quotation

    def validate(self, attrs):
        attrs = super().validate(attrs)
        quotation = attrs.get("quotation", getattr(self.instance, "quotation", None))
        items = attrs.get("items")
        if quotation and items is not None:
            quote_items = list(
                quotation.items.order_by("pk").values_list(
                    "description", "quantity", "unit_price"
                )
            )
            submitted_items = [
                (item["description"], item["quantity"], item["unit_price"])
                for item in items
            ]
            if submitted_items != quote_items:
                raise serializers.ValidationError(
                    {"items": "Purchase order items and prices must match the accepted quotation."}
                )
        if self.instance and self.instance.approved:
            raise serializers.ValidationError(
                "Approved purchase orders cannot be changed."
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items")
        quotation = validated_data["quotation"]
        validated_data["supplier"] = quotation.supplier
        validated_data["requisition"] = quotation.requisition
        order = PurchaseOrder.objects.create(total_amount=Decimal("0.00"), **validated_data)
        PurchaseOrderItem.objects.bulk_create(
            [
                PurchaseOrderItem(purchase_order=order, **item)
                for item in items
            ]
        )
        order.total_amount = sum(
            (item["quantity"] * item["unit_price"] for item in items),
            Decimal("0.00"),
        )
        order.save(update_fields=["total_amount", "updated_at"])
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            PurchaseOrderItem.objects.bulk_create(
                [
                    PurchaseOrderItem(purchase_order=instance, **item)
                    for item in items
                ]
            )
            instance.total_amount = sum(
                (
                    item["quantity"] * item["unit_price"]
                    for item in items
                ),
                Decimal("0.00"),
            )
            instance.save(update_fields=["total_amount", "updated_at"])
        return instance
