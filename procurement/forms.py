from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.contrib.auth import get_user_model
from accounts.models import Role
from .models import (
    SupplierCategory,
    Supplier,
    ProcurementDepartment,
    ProcurementStatus,
    ProcurementWorkflowRule,
    ProcurementPlan,
    PurchaseRequisition,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
)


class DateInput(forms.DateInput):
    input_type = 'date'


class SupplierCategoryForm(forms.ModelForm):
    class Meta:
        model = SupplierCategory
        fields = ["name", "description"]


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "category", "email", "phone", "address", "is_blacklisted"]


class ProcurementDepartmentForm(forms.ModelForm):
    class Meta:
        model = ProcurementDepartment
        fields = ["name", "slug"]


class ProcurementStatusForm(forms.ModelForm):
    protected_slugs = {"draft", "submitted", "approved", "rejected", "returned"}

    class Meta:
        model = ProcurementStatus
        fields = ["name", "slug", "is_default"]

    def clean_slug(self):
        slug = self.cleaned_data["slug"]
        if (
            self.instance.pk
            and self.instance.slug in self.protected_slugs
            and slug != self.instance.slug
        ):
            raise ValidationError("The slug of a core requisition status cannot be changed.")
        return slug


class ProcurementWorkflowRuleForm(forms.ModelForm):
    class Meta:
        model = ProcurementWorkflowRule
        fields = [
            "from_status",
            "to_status",
            "department",
            "action_label",
            "approver_type",
            "approver_role",
            "approver_user",
            "requires_reason",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["approver_role"].queryset = Role.objects.order_by("name")
        self.fields["approver_user"].queryset = (
            get_user_model().objects.filter(is_active=True).order_by("username")
        )

    def clean(self):
        cleaned_data = super().clean()
        from_status = cleaned_data.get("from_status")
        to_status = cleaned_data.get("to_status")
        approver_type = cleaned_data.get("approver_type")
        approver_role = cleaned_data.get("approver_role")
        approver_user = cleaned_data.get("approver_user")
        department = cleaned_data.get("department")

        if from_status and to_status and from_status == to_status:
            self.add_error("to_status", "A workflow step must move to a different status.")
        if department and approver_type != ProcurementWorkflowRule.ApproverType.USER:
            self.add_error(
                "approver_type",
                "Department-specific rules must name an approver because user accounts are not assigned to procurement departments.",
            )
        if approver_type == ProcurementWorkflowRule.ApproverType.ROLE and not approver_role:
            self.add_error("approver_role", "Select the role responsible for this step.")
        if approver_type == ProcurementWorkflowRule.ApproverType.USER and not approver_user:
            self.add_error("approver_user", "Select the user responsible for this step.")
        if approver_type != ProcurementWorkflowRule.ApproverType.ROLE and approver_role:
            self.add_error("approver_role", "Choose Role as the approver type to assign a role.")
        if approver_type != ProcurementWorkflowRule.ApproverType.USER and approver_user:
            self.add_error("approver_user", "Choose Specific user as the approver type to assign a user.")

        if from_status and to_status:
            duplicates = ProcurementWorkflowRule.objects.filter(
                from_status=from_status,
                to_status=to_status,
                department=department,
            )
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error(
                    "to_status",
                    "A workflow rule for this status change and department already exists.",
                )
        return cleaned_data


class ProcurementPlanForm(forms.ModelForm):
    class Meta:
        model = ProcurementPlan
        fields = ["title", "department", "fiscal_year"]


class PurchaseRequisitionForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequisition
        fields = ["title", "description", "department", "total_amount", "required_by", "attachments"]
        widgets = {
            'required_by': DateInput(),
        }


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["quotation"]
        widgets = {
            "quotation": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        is_editing = not self.instance._state.adding
        self.fields["quotation"].queryset = PurchaseQuotation.objects.filter(
            deleted_at__isnull=True,
            status=PurchaseQuotation.Status.ACCEPTED,
            requisition__deleted_at__isnull=True,
            requisition__status__slug="approved",
            purchase_orders__isnull=True,
        ).filter(
            Q(valid_until__isnull=True)
            | Q(valid_until__gte=timezone.localdate()),
            document__gt="",
        )
        self.fields["quotation"].queryset = self.fields["quotation"].queryset.select_related(
            "supplier",
            "requisition",
        ).distinct()
        self.fields["quotation"].label = "Accepted supplier quotation"
        self.fields["quotation"].empty_label = "Select an accepted quotation"
        self.fields["quotation"].required = not is_editing
        if is_editing and not self.instance.quotation_id:
            self.fields["supplier"] = forms.ModelChoiceField(
                queryset=Supplier.objects.filter(
                    deleted_at__isnull=True,
                    is_blacklisted=False,
                ),
                initial=self.instance.supplier,
                widget=forms.Select(attrs={"class": "form-select"}),
            )
            self.fields["requisition"] = forms.ModelChoiceField(
                queryset=PurchaseRequisition.objects.filter(
                    deleted_at__isnull=True,
                    status__slug="approved",
                ),
                initial=self.instance.requisition,
                required=False,
                widget=forms.Select(attrs={"class": "form-select"}),
            )

    def clean(self):
        cleaned_data = super().clean()
        quotation = cleaned_data.get("quotation")
        supplier = quotation.supplier if quotation else None
        is_editing_legacy_order = (
            not self.instance._state.adding and not self.instance.quotation_id
        )
        if is_editing_legacy_order and not quotation:
            supplier = cleaned_data.get("supplier")
            requisition = cleaned_data.get("requisition")
            if requisition and (
                not requisition.status or requisition.status.slug != "approved"
            ):
                self.add_error("requisition", "Only approved requisitions can be ordered.")
            if requisition and requisition.purchase_orders.exclude(
                pk=self.instance.pk
            ).filter(deleted_at__isnull=True).exists():
                self.add_error("requisition", "This requisition already has a purchase order.")
        if supplier and supplier.is_blacklisted:
            self.add_error(
                "quotation" if quotation else "supplier",
                "Blacklisted suppliers cannot receive orders.",
            )
        if quotation and quotation.purchase_orders.exclude(
            pk=self.instance.pk or None
        ).filter(deleted_at__isnull=True).exists():
            self.add_error(
                "quotation",
                "A purchase order already exists for this quotation.",
            )
        if quotation and quotation.valid_until and quotation.valid_until < timezone.localdate():
            self.add_error("quotation", "The accepted supplier quotation has expired.")
        return cleaned_data

    def save(self, commit=True):
        order = super().save(commit=False)
        quotation = self.cleaned_data["quotation"]
        if quotation:
            order.supplier = quotation.supplier
            order.requisition = quotation.requisition
        elif "supplier" in self.cleaned_data:
            order.supplier = self.cleaned_data["supplier"]
            order.requisition = self.cleaned_data.get("requisition")
        if commit:
            order.save()
            self.save_m2m()
        return order


class PurchaseQuotationForm(forms.ModelForm):
    class Meta:
        model = PurchaseQuotation
        fields = [
            "supplier",
            "requisition",
            "reference",
            "date_received",
            "valid_until",
            "document",
            "notes",
        ]
        widgets = {
            "date_received": DateInput(),
            "valid_until": DateInput(),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(
            deleted_at__isnull=True,
            is_blacklisted=False,
        )
        self.fields["requisition"].queryset = PurchaseRequisition.objects.filter(
            deleted_at__isnull=True,
            status__slug="approved",
        )
        self.fields["requisition"].required = True
        self.fields["document"].required = True
        self.fields["document"].help_text = (
            "Attach the original supplier quotation (PDF, Word, Excel, or image)."
        )

    def clean(self):
        cleaned_data = super().clean()
        supplier = cleaned_data.get("supplier")
        if supplier and supplier.is_blacklisted:
            self.add_error("supplier", "Blacklisted suppliers cannot submit quotations.")
        return cleaned_data


class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['description', 'quantity', 'unit_price']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Item description'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity < 1:
            raise forms.ValidationError("Quantity must be at least one.")
        return quantity

    def clean_unit_price(self):
        unit_price = self.cleaned_data["unit_price"]
        if unit_price <= 0:
            raise forms.ValidationError("Unit price must be greater than zero.")
        return unit_price


class BasePurchaseOrderItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active_items = [
            form
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        if not active_items:
            raise ValidationError("A purchase order must contain at least one item.")


PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    formset=BasePurchaseOrderItemFormSet,
    fields=('description', 'quantity', 'unit_price'),
    extra=1,
    can_delete=True,
)


class PurchaseQuotationItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseQuotationItem
        fields = ["description", "quantity", "unit_price"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity < 1:
            raise forms.ValidationError("Quantity must be at least one.")
        return quantity

    def clean_unit_price(self):
        unit_price = self.cleaned_data["unit_price"]
        if unit_price <= 0:
            raise forms.ValidationError("Unit price must be greater than zero.")
        return unit_price


class BasePurchaseQuotationItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if not any(
            form.cleaned_data and not form.cleaned_data.get("DELETE")
            for form in self.forms
        ):
            raise ValidationError("A supplier quotation must contain at least one item.")


PurchaseQuotationItemFormSet = inlineformset_factory(
    PurchaseQuotation,
    PurchaseQuotationItem,
    form=PurchaseQuotationItemForm,
    formset=BasePurchaseQuotationItemFormSet,
    fields=("description", "quantity", "unit_price"),
    extra=1,
    can_delete=True,
)
