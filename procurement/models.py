import uuid
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SoftDeleteModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save()

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class SupplierCategory(SoftDeleteModel):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _('Supplier Category')
        verbose_name_plural = _('Supplier Categories')

    def __str__(self):
        return self.name


class Supplier(SoftDeleteModel):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(SupplierCategory, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_blacklisted = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='suppliers_created')

    class Meta:
        verbose_name = _('Supplier')
        verbose_name_plural = _('Suppliers')

    def __str__(self):
        return self.name


class ProcurementDepartment(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)

    class Meta:
        verbose_name = _('Procurement Department')
        verbose_name_plural = _('Procurement Departments')

    def __str__(self):
        return self.name


class ProcurementStatus(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('Procurement Status')
        verbose_name_plural = _('Procurement Statuses')

    def __str__(self):
        return self.name


class ProcurementWorkflowRule(models.Model):
    class ApproverType(models.TextChoices):
        PROCUREMENT_MANAGER = "procurement_manager", _("Procurement manager")
        ROLE = "role", _("Role")
        USER = "user", _("Specific user")

    from_status = models.ForeignKey(
        ProcurementStatus,
        on_delete=models.PROTECT,
        related_name="outgoing_workflow_rules",
    )
    to_status = models.ForeignKey(
        ProcurementStatus,
        on_delete=models.PROTECT,
        related_name="incoming_workflow_rules",
    )
    department = models.ForeignKey(
        ProcurementDepartment,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="workflow_rules",
        help_text=_("Leave blank to use this rule for departments without a specific rule."),
    )
    action_label = models.CharField(max_length=120)
    approver_type = models.CharField(
        max_length=32,
        choices=ApproverType.choices,
        default=ApproverType.PROCUREMENT_MANAGER,
    )
    approver_role = models.ForeignKey(
        "accounts.Role",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="procurement_workflow_rules",
    )
    approver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="procurement_workflow_rules",
    )
    requires_reason = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("from_status__name", "department__name", "action_label")
        verbose_name = _("Procurement workflow rule")
        verbose_name_plural = _("Procurement workflow rules")

    def __str__(self):
        scope = self.department.name if self.department_id else _("All departments")
        return f"{self.action_label} ({self.from_status} → {self.to_status}, {scope})"


class ProcurementPlan(SoftDeleteModel):
    title = models.CharField(max_length=255)
    department = models.ForeignKey(
        ProcurementDepartment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='plans',
    )
    fiscal_year = models.CharField(max_length=20)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _('Procurement Plan')
        verbose_name_plural = _('Procurement Plans')

    def __str__(self):
        return self.title


class PurchaseRequisition(SoftDeleteModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    department = models.ForeignKey(
        ProcurementDepartment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='requisitions',
    )
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey(
        ProcurementStatus,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='requisitions',
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    required_by = models.DateField(blank=True, null=True)
    attachments = models.FileField(upload_to='procurement/attachments/', blank=True, null=True)

    class Meta:
        verbose_name = _('Purchase Requisition')
        verbose_name_plural = _('Purchase Requisitions')

    def __str__(self):
        return self.title


class PurchaseRequisitionStatusHistory(models.Model):
    requisition = models.ForeignKey(
        PurchaseRequisition,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=40, blank=True)
    to_status = models.CharField(max_length=40)
    comment = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requisition_status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-changed_at",)


class PurchaseOrder(SoftDeleteModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    requisition = models.ForeignKey(PurchaseRequisition, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders')
    quotation = models.ForeignKey(
        "PurchaseQuotation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    order_date = models.DateField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = _('Purchase Order')
        verbose_name_plural = _('Purchase Orders')
        constraints = [
            models.UniqueConstraint(
                fields=("quotation",),
                condition=models.Q(quotation__isnull=False, deleted_at__isnull=True),
                name="unique_active_purchase_order_per_quotation",
            )
        ]

    @property
    def order_number(self):
        return f"PO-{self.id.hex[:8].upper()}"

    @property
    def items_total(self):
        return sum(item.line_total for item in self.items.all())

    @property
    def supplier_address(self):
        return self.supplier.address or ''

    def __str__(self):
        return f"{self.order_number} - {self.supplier.name}"


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Purchase Order Item')
        verbose_name_plural = _('Purchase Order Items')

    def __str__(self):
        return f"{self.description} x {self.quantity}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class PurchaseQuotation(SoftDeleteModel):
    class Status(models.TextChoices):
        RECEIVED = "received", _("Received")
        UNDER_REVIEW = "under_review", _("Under review")
        ACCEPTED = "accepted", _("Accepted")
        DECLINED = "declined", _("Declined")
        EXPIRED = "expired", _("Expired")

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="quotations",
    )
    requisition = models.ForeignKey(
        PurchaseRequisition,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotations",
    )
    reference = models.CharField(max_length=120, blank=True)
    document = models.FileField(
        upload_to="procurement/quotations/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "png",
                    "jpg",
                    "jpeg",
                ]
            )
        ],
    )
    date_received = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_quotations_created",
    )

    class Meta:
        ordering = ("-date_received", "-created_at")
        verbose_name = _("Supplier Quotation")
        verbose_name_plural = _("Supplier Quotations")
        constraints = [
            models.UniqueConstraint(
                fields=("requisition",),
                condition=models.Q(
                    requisition__isnull=False,
                    status="accepted",
                    deleted_at__isnull=True,
                ),
                name="unique_selected_quotation_per_requisition",
            )
        ]

    @property
    def quotation_number(self):
        return f"QUO-{self.pk.hex[:8].upper()}"

    @property
    def items_total(self):
        return sum(item.line_total for item in self.items.all())

    def __str__(self):
        return f"{self.quotation_number} - {self.supplier.name}"


class PurchaseQuotationItem(models.Model):
    quotation = models.ForeignKey(
        PurchaseQuotation,
        on_delete=models.CASCADE,
        related_name="items",
    )
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Supplier Quotation Item")
        verbose_name_plural = _("Supplier Quotation Items")

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.description} x {self.quantity}"
