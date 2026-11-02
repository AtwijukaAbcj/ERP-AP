from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
import csv
import mimetypes
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from .models import (
    SupplierCategory,
    Supplier,
    ProcurementDepartment,
    ProcurementStatus,
    ProcurementWorkflowRule,
    ProcurementPlan,
    PurchaseRequisition,
    PurchaseRequisitionStatusHistory,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
)
from .forms import (
    SupplierCategoryForm,
    SupplierForm,
    ProcurementDepartmentForm,
    ProcurementStatusForm,
    ProcurementWorkflowRuleForm,
    ProcurementPlanForm,
    PurchaseRequisitionForm,
    PurchaseOrderForm,
    PurchaseOrderItemFormSet,
    PurchaseQuotationForm,
    PurchaseQuotationItemFormSet,
)
from .permissions import has_procurement_access, procurement_permission_required


@login_required
@procurement_permission_required("procurement_dashboard")
def procurement_dashboard(request):
    return render(request, "procurement/dashboard.html", {
        "supplier_category_count": SupplierCategory.objects.filter(deleted_at__isnull=True).count(),
        "supplier_count": Supplier.objects.filter(deleted_at__isnull=True).count(),
        "department_count": ProcurementDepartment.objects.count(),
        "status_count": ProcurementStatus.objects.count(),
        "plan_count": ProcurementPlan.objects.filter(deleted_at__isnull=True).count(),
        "requisition_count": PurchaseRequisition.objects.filter(deleted_at__isnull=True).count(),
        "order_count": PurchaseOrder.objects.filter(deleted_at__isnull=True).count(),
        "quotation_count": PurchaseQuotation.objects.filter(deleted_at__isnull=True).count(),
    })


@login_required
@procurement_permission_required("procurement_supplier_categories")
def supplier_category_list(request):
    categories = SupplierCategory.objects.filter(deleted_at__isnull=True)
    return render(request, "procurement/supplier_category_list.html", {"categories": categories})


@login_required
@procurement_permission_required("procurement_departments", "procurement_plans")
def procurement_department_list(request):
    departments = ProcurementDepartment.objects.all()
    return render(request, "procurement/department_list.html", {"departments": departments})


@login_required
@procurement_permission_required("procurement_departments_add", "procurement_plans_add")
def procurement_department_add(request):
    if request.method == "POST":
        form = ProcurementDepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("procurement:procurement_department_list")
    else:
        form = ProcurementDepartmentForm()

    return render(request, "procurement/department_add.html", {"form": form})


@login_required
@procurement_permission_required("procurement_departments_edit", "procurement_plans_edit")
def procurement_department_edit(request, department_id):
    department = get_object_or_404(ProcurementDepartment, id=department_id)
    if request.method == "POST":
        form = ProcurementDepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            return redirect("procurement:procurement_department_list")
    else:
        form = ProcurementDepartmentForm(instance=department)
    return render(request, "procurement/department_add.html", {"form": form})


@login_required
@require_POST
@procurement_permission_required("procurement_departments_delete", "procurement_plans_delete")
def procurement_department_delete(request, department_id):
    department = get_object_or_404(ProcurementDepartment, id=department_id)
    if department.workflow_rules.exists():
        messages.error(request, "A department with configured workflow rules cannot be deleted.")
        return redirect("procurement:procurement_department_list")
    department.delete()
    messages.success(request, "Procurement department deleted.")
    return redirect("procurement:procurement_department_list")


@login_required
@procurement_permission_required("procurement_statuses", "procurement_plans")
def procurement_status_list(request):
    statuses = ProcurementStatus.objects.all()
    return render(request, "procurement/status_list.html", {"statuses": statuses})


@login_required
@procurement_permission_required("procurement_statuses", "procurement_requisitions_edit")
def procurement_status_add(request):
    if request.method == "POST":
        form = ProcurementStatusForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("procurement:procurement_status_list")
    else:
        form = ProcurementStatusForm()

    return render(request, "procurement/status_add.html", {"form": form, "is_editing": False})


@login_required
@procurement_permission_required("procurement_statuses", "procurement_requisitions_edit")
def procurement_status_edit(request, status_id):
    status = get_object_or_404(ProcurementStatus, id=status_id)
    if request.method == "POST":
        form = ProcurementStatusForm(request.POST, instance=status)
        if form.is_valid():
            form.save()
            return redirect("procurement:procurement_status_list")
    else:
        form = ProcurementStatusForm(instance=status)
    return render(request, "procurement/status_add.html", {"form": form, "is_editing": True})


@login_required
@require_POST
@procurement_permission_required("procurement_statuses", "procurement_requisitions_edit")
def procurement_status_delete(request, status_id):
    status = get_object_or_404(ProcurementStatus, id=status_id)
    if status.slug in {"draft", "submitted", "approved", "rejected", "returned"}:
        messages.error(request, "Core requisition statuses cannot be deleted.")
        return redirect("procurement:procurement_status_list")
    if status.requisitions.exists() or status.incoming_workflow_rules.exists() or status.outgoing_workflow_rules.exists():
        messages.error(request, "A status used by requisitions or workflow rules cannot be deleted.")
        return redirect("procurement:procurement_status_list")
    status.delete()
    messages.success(request, "Procurement status deleted.")
    return redirect("procurement:procurement_status_list")


@login_required
@procurement_permission_required("procurement_workflows", "procurement_requisitions_edit")
def procurement_workflow_rule_list(request):
    rules = ProcurementWorkflowRule.objects.select_related(
        "from_status",
        "to_status",
        "department",
        "approver_role",
        "approver_user",
    )
    return render(
        request,
        "procurement/workflow_rule_list.html",
        {"rules": rules},
    )


@login_required
@procurement_permission_required("procurement_workflows", "procurement_requisitions_edit")
def procurement_workflow_rule_add(request):
    if request.method == "POST":
        form = ProcurementWorkflowRuleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Procurement workflow rule saved.")
            return redirect("procurement:procurement_workflow_rule_list")
    else:
        form = ProcurementWorkflowRuleForm()
    return render(
        request,
        "procurement/workflow_rule_add.html",
        {"form": form, "is_editing": False},
    )


@login_required
@procurement_permission_required("procurement_workflows", "procurement_requisitions_edit")
def procurement_workflow_rule_edit(request, rule_id):
    rule = get_object_or_404(ProcurementWorkflowRule, pk=rule_id)
    if request.method == "POST":
        form = ProcurementWorkflowRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, "Procurement workflow rule updated.")
            return redirect("procurement:procurement_workflow_rule_list")
    else:
        form = ProcurementWorkflowRuleForm(instance=rule)
    return render(
        request,
        "procurement/workflow_rule_add.html",
        {"form": form, "is_editing": True},
    )


@login_required
@require_POST
@procurement_permission_required("procurement_workflows", "procurement_requisitions_edit")
def procurement_workflow_rule_delete(request, rule_id):
    rule = get_object_or_404(ProcurementWorkflowRule, pk=rule_id)
    rule.delete()
    messages.success(request, "Procurement workflow rule deleted.")
    return redirect("procurement:procurement_workflow_rule_list")


@login_required
@procurement_permission_required("procurement_supplier_categories_add")
def supplier_category_add(request):
    if request.method == "POST":
        form = SupplierCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("procurement:supplier_category_list")
    else:
        form = SupplierCategoryForm()

    return render(request, "procurement/supplier_category_add.html", {"form": form})


@login_required
@procurement_permission_required("procurement_suppliers")
def supplier_list(request):
    suppliers = Supplier.objects.filter(deleted_at__isnull=True).select_related("category")
    return render(request, "procurement/supplier_list.html", {"suppliers": suppliers})


@login_required
@procurement_permission_required("procurement_suppliers_add")
def supplier_add(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.created_by = request.user
            supplier.save()
            return redirect("procurement:supplier_list")
    else:
        form = SupplierForm()

    return render(request, "procurement/supplier_add.html", {"form": form})


@login_required
@procurement_permission_required("procurement_plans")
def procurement_plan_list(request):
    plans = ProcurementPlan.objects.filter(deleted_at__isnull=True)
    return render(request, "procurement/procurement_plan_list.html", {"plans": plans, "request": request})


@login_required
@require_POST
@procurement_permission_required("procurement_plans_approve")
def procurement_plan_approve(request, plan_id):
    plan = get_object_or_404(
        ProcurementPlan,
        id=plan_id,
        deleted_at__isnull=True,
    )
    if not has_procurement_access(request.user, "procurement_plans_approve"):
        return HttpResponseForbidden("You are not authorized to approve procurement plans.")

    plan.approved = True
    plan.approved_at = timezone.now()
    plan.save()
    messages.success(request, "Procurement plan approved.")
    return redirect('procurement:procurement_plan_list')


@login_required
@procurement_permission_required("procurement_plans_add")
def procurement_plan_add(request):
    if request.method == "POST":
        form = ProcurementPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.requested_by = request.user
            plan.approved = False
            plan.approved_at = None
            plan.save()
            return redirect("procurement:procurement_plan_list")
    else:
        form = ProcurementPlanForm()

    return render(request, "procurement/procurement_plan_add.html", {"form": form})


@login_required
@procurement_permission_required("procurement_plans_edit")
def procurement_plan_edit(request, plan_id):
    plan = get_object_or_404(
        ProcurementPlan,
        id=plan_id,
        deleted_at__isnull=True,
    )
    if request.method == "POST":
        form = ProcurementPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            return redirect("procurement:procurement_plan_list")
    else:
        form = ProcurementPlanForm(instance=plan)
    return render(request, "procurement/procurement_plan_add.html", {"form": form})


@login_required
@require_POST
@procurement_permission_required("procurement_plans_delete")
def procurement_plan_delete(request, plan_id):
    plan = get_object_or_404(
        ProcurementPlan,
        id=plan_id,
        deleted_at__isnull=True,
    )
    plan.soft_delete()
    messages.success(request, "Procurement plan deleted.")
    return redirect("procurement:procurement_plan_list")


@login_required
@procurement_permission_required("procurement_requisitions")
def purchase_requisition_list(request):
    requisitions = list(PurchaseRequisition.objects.filter(
        deleted_at__isnull=True,
    ).select_related("status", "department", "requested_by").prefetch_related(
        "status_history__changed_by",
        "quotations",
    ))
    workflow_rules = list(
        ProcurementWorkflowRule.objects.select_related(
            "from_status",
            "to_status",
            "department",
            "approver_role",
            "approver_user",
        )
    )
    can_review = _is_procurement_manager(request.user)
    can_submit = (
        request.user.has_permission("procurement_requisitions_add")
        or request.user.has_permission("procurement_requisitions_edit")
        or can_review
    )
    for requisition in requisitions:
        current_slug = requisition.status.slug if requisition.status else "draft"
        matching_rules = _matching_workflow_rules(
            workflow_rules,
            current_slug,
            requisition.department_id,
        )
        requisition.available_workflow_rules = [
            rule
            for rule in matching_rules
            if _user_can_apply_workflow_rule(request.user, requisition, rule)
        ]
    return render(
        request,
        "procurement/purchase_requisition_list.html",
        {
            "requisitions": requisitions,
            "request": request,
            "can_review": can_review,
            "can_submit": can_submit,
        },
    )


def _is_procurement_manager(user):
    return (
        user.is_superuser
        or user.is_procurement_manager
        or user.has_role("procurement_manager")
    )


def _matching_workflow_rules(rules, from_status_slug, department_id):
    matching = [
        rule
        for rule in rules
        if rule.from_status.slug == from_status_slug
    ]
    if department_id is not None:
        department_rules = [
            rule for rule in matching if rule.department_id == department_id
        ]
        if department_rules:
            return [rule for rule in department_rules if rule.is_active]
    return [
        rule
        for rule in matching
        if rule.department_id is None and rule.is_active
    ]


def _user_can_apply_workflow_rule(user, requisition, rule):
    if requisition.requested_by_id == user.pk:
        return False
    if (
        rule.department_id
        and rule.approver_type != ProcurementWorkflowRule.ApproverType.USER
    ):
        return False
    if user.is_superuser:
        return True
    if rule.approver_type == ProcurementWorkflowRule.ApproverType.PROCUREMENT_MANAGER:
        return _is_procurement_manager(user)
    if rule.approver_type == ProcurementWorkflowRule.ApproverType.ROLE:
        return bool(user.role_id and user.role_id == rule.approver_role_id)
    if rule.approver_type == ProcurementWorkflowRule.ApproverType.USER:
        return user.pk == rule.approver_user_id
    return False


@login_required
@require_POST
def purchase_requisition_approve(request, requisition_id):
    return _transition_requisition(request, requisition_id, "approved")


@login_required
@require_POST
def purchase_requisition_transition(request, requisition_id):
    action = request.POST.get("action", "")
    if action.startswith("rule:"):
        try:
            rule_id = int(action.split(":", 1)[1])
        except ValueError:
            messages.error(request, "Choose a valid requisition action.")
            return redirect("procurement:purchase_requisition_list")
        return _transition_requisition(
            request,
            requisition_id,
            workflow_rule_id=rule_id,
        )
    transitions = {
        "submit": "submitted",
        "send_for_approval": "pending_approval",
        "approve": "approved",
        "reject": "rejected",
        "return": "returned",
    }
    to_status = transitions.get(action)
    if not to_status:
        messages.error(request, "Choose a valid requisition action.")
        return redirect("procurement:purchase_requisition_list")
    return _transition_requisition(request, requisition_id, to_status)


def _transition_requisition(request, requisition_id, to_status=None, workflow_rule_id=None):
    requisition = get_object_or_404(
        PurchaseRequisition.objects.select_related("status", "department"),
        id=requisition_id,
        deleted_at__isnull=True,
    )
    comment = request.POST.get("comment", "").strip()
    submission = to_status == "submitted" and workflow_rule_id is None
    with transaction.atomic():
        requisition = PurchaseRequisition.objects.select_for_update().get(
            pk=requisition.pk,
            deleted_at__isnull=True,
        )
        current_status = requisition.status.slug if requisition.status else "draft"
        selected_rule = None
        if submission:
            if current_status not in {"draft", "returned"}:
                messages.error(request, "Only draft or returned requisitions can be submitted.")
                return redirect("procurement:purchase_requisition_list")
            manager = _is_procurement_manager(request.user)
            if (
                not request.user.has_permission("procurement_requisitions_add")
                and not request.user.has_permission("procurement_requisitions_edit")
                and not manager
            ):
                return HttpResponseForbidden("You are not authorized to submit requisitions.")
            if requisition.requested_by_id != request.user.pk and not manager:
                return HttpResponseForbidden("Only the requester or a procurement manager can submit this requisition.")
        else:
            rules = list(
                ProcurementWorkflowRule.objects.select_related(
                    "from_status",
                    "to_status",
                    "department",
                    "approver_role",
                    "approver_user",
                )
            )
            applicable_rules = _matching_workflow_rules(
                rules,
                current_status,
                requisition.department_id,
            )
            if workflow_rule_id is not None:
                selected_rule = next(
                    (
                        rule
                        for rule in applicable_rules
                        if rule.pk == workflow_rule_id
                    ),
                    None,
                )
            else:
                eligible_rules = [
                    rule
                    for rule in applicable_rules
                    if rule.to_status.slug == to_status
                    and _user_can_apply_workflow_rule(
                        request.user,
                        requisition,
                        rule,
                    )
                ]
                selected_rule = eligible_rules[0] if eligible_rules else None
            if selected_rule is None:
                return HttpResponseForbidden(
                    "You are not authorized to perform this configured workflow action."
                )
            if not _user_can_apply_workflow_rule(request.user, requisition, selected_rule):
                return HttpResponseForbidden(
                    "You are not authorized to perform this configured workflow action."
                )
            to_status = selected_rule.to_status.slug
            if (
                selected_rule.requires_reason
                or to_status in {"approved", "rejected", "returned"}
            ) and not comment:
                messages.error(request, "A reason is required for this requisition decision.")
                return redirect("procurement:purchase_requisition_list")
            if to_status == "approved" and requisition.purchase_orders.filter(
                deleted_at__isnull=True
            ).exists():
                messages.error(request, "A requisition with an existing purchase order cannot be re-approved.")
                return redirect("procurement:purchase_requisition_list")

        status = (
            selected_rule.to_status
            if selected_rule
            else ProcurementStatus.objects.filter(slug=to_status).first()
        )
        if status is None:
            messages.error(request, "The destination status for this workflow action no longer exists.")
            return redirect("procurement:purchase_requisition_list")
        requisition.status = status
        requisition.save(update_fields=["status", "updated_at"])
        PurchaseRequisitionStatusHistory.objects.create(
            requisition=requisition,
            from_status=current_status,
            to_status=to_status,
            comment=comment,
            changed_by=request.user,
        )
    messages.success(
        request,
        f"Purchase requisition moved to {status.name}.",
    )
    return redirect("procurement:purchase_requisition_list")


@login_required
@procurement_permission_required("procurement_requisitions_add")
def purchase_requisition_add(request):
    if request.method == "POST":
        form = PurchaseRequisitionForm(request.POST, request.FILES)
        if form.is_valid():
            requisition = form.save(commit=False)
            requisition.requested_by = request.user
            requisition.status, _ = ProcurementStatus.objects.get_or_create(
                slug="draft",
                defaults={"name": "Draft", "is_default": True},
            )
            with transaction.atomic():
                requisition.save()
                PurchaseRequisitionStatusHistory.objects.create(
                    requisition=requisition,
                    to_status="draft",
                    comment="Requisition created.",
                    changed_by=request.user,
                )
            return redirect("procurement:purchase_requisition_list")
    else:
        form = PurchaseRequisitionForm()

    return render(request, "procurement/purchase_requisition_add.html", {"form": form})


@login_required
@procurement_permission_required("procurement_requisitions_edit")
def purchase_requisition_edit(request, requisition_id):
    requisition = get_object_or_404(
        PurchaseRequisition,
        id=requisition_id,
        deleted_at__isnull=True,
    )
    if (
        (requisition.status and requisition.status.slug not in {"draft", "returned"})
        or requisition.purchase_orders.filter(deleted_at__isnull=True).exists()
    ):
        return HttpResponseForbidden("Only draft or returned requisitions without orders can be edited.")
    if request.method == "POST":
        form = PurchaseRequisitionForm(request.POST, request.FILES, instance=requisition)
        if form.is_valid():
            form.save()
            return redirect("procurement:purchase_requisition_list")
    else:
        form = PurchaseRequisitionForm(instance=requisition)
    return render(request, "procurement/purchase_requisition_add.html", {"form": form})


@login_required
@require_POST
@procurement_permission_required("procurement_requisitions_delete")
def purchase_requisition_delete(request, requisition_id):
    requisition = get_object_or_404(
        PurchaseRequisition,
        id=requisition_id,
        deleted_at__isnull=True,
    )
    if requisition.purchase_orders.filter(deleted_at__isnull=True).exists():
        messages.error(request, "A requisition with purchase orders cannot be deleted.")
        return redirect("procurement:purchase_requisition_list")
    requisition.soft_delete()
    messages.success(request, "Purchase requisition deleted.")
    return redirect("procurement:purchase_requisition_list")


@login_required
@procurement_permission_required("procurement_requisitions_export")
def export_purchase_requisition_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="purchase_requisitions.csv"'
    writer = csv.writer(response)
    writer.writerow(['Title', 'Department', 'Requested By', 'Status', 'Total Amount', 'Required By'])

    for requisition in PurchaseRequisition.objects.filter(deleted_at__isnull=True).select_related('department', 'requested_by', 'status'):
        writer.writerow([
            requisition.title,
            requisition.department.name if requisition.department else '',
            requisition.requested_by.get_full_name if requisition.requested_by else '',
            requisition.status.name if requisition.status else '',
            requisition.total_amount,
            requisition.required_by,
        ])
    return response


@login_required
@procurement_permission_required("procurement_requisitions_export")
def export_purchase_requisition_excel(request):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Purchase Requisitions"
    worksheet.append(
        ["Title", "Department", "Requested By", "Status", "Total Amount", "Required By"]
    )
    requisitions = PurchaseRequisition.objects.filter(
        deleted_at__isnull=True,
    ).select_related("department", "requested_by", "status")
    for requisition in requisitions:
        worksheet.append(
            [
                requisition.title,
                requisition.department.name if requisition.department else "",
                requisition.requested_by.get_full_name if requisition.requested_by else "",
                requisition.status.name if requisition.status else "",
                requisition.total_amount,
                requisition.required_by,
            ]
        )
    output = BytesIO()
    workbook.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        'attachment; filename="purchase_requisitions.xlsx"'
    )
    return response


@login_required
@procurement_permission_required("procurement_orders")
def purchase_order_list(request):
    orders = PurchaseOrder.objects.filter(
        deleted_at__isnull=True,
    ).select_related("supplier", "requisition", "quotation")
    return render(request, "procurement/purchase_order_list.html", {"orders": orders, "request": request})


@login_required
@require_POST
@procurement_permission_required("procurement_orders_approve")
def purchase_order_approve(request, order_id):
    order = get_object_or_404(
        PurchaseOrder,
        id=order_id,
        deleted_at__isnull=True,
    )
    if not has_procurement_access(request.user, "procurement_orders_approve"):
        return HttpResponseForbidden("You are not authorized to approve purchase orders.")

    if order.approved:
        messages.info(request, "This purchase order is already approved.")
        return redirect('procurement:purchase_order_list')
    if order.items.count() == 0 or order.items_total <= 0:
        messages.error(request, "A purchase order must have items with positive value before approval.")
        return redirect('procurement:purchase_order_list')
    if order.supplier.is_blacklisted or order.supplier.deleted_at is not None:
        messages.error(request, "Orders cannot be approved for an inactive or blacklisted supplier.")
        return redirect('procurement:purchase_order_list')
    if order.requisition_id and (
        order.requisition.deleted_at is not None
        or not order.requisition.status
        or order.requisition.status.slug != "approved"
    ):
        messages.error(request, "The linked requisition is no longer approved.")
        return redirect('procurement:purchase_order_list')
    if order.requisition_id and (
        not order.quotation_id
        or order.quotation.deleted_at is not None
        or order.quotation.status != PurchaseQuotation.Status.ACCEPTED
        or order.quotation.requisition_id != order.requisition_id
        or order.quotation.supplier_id != order.supplier_id
        or order.items_total != order.quotation.total_amount
    ):
        messages.error(request, "The purchase order must match its accepted supplier quotation.")
        return redirect('procurement:purchase_order_list')
    if order.quotation_id and (
        order.quotation.valid_until
        and order.quotation.valid_until < timezone.localdate()
    ):
        messages.error(request, "The selected supplier quotation has expired.")
        return redirect('procurement:purchase_order_list')
    if order.quotation_id:
        order_lines = list(
            order.items.order_by("pk").values_list(
                "description", "quantity", "unit_price"
            )
        )
        quotation_lines = list(
            order.quotation.items.order_by("pk").values_list(
                "description", "quantity", "unit_price"
            )
        )
        if order_lines != quotation_lines:
            messages.error(request, "The purchase order line items must match the accepted quotation.")
            return redirect('procurement:purchase_order_list')
    if (
        order.requisition_id
        and order.requisition.total_amount > 0
        and order.items_total > order.requisition.total_amount
    ):
        messages.error(request, "The purchase order exceeds the approved requisition amount.")
        return redirect('procurement:purchase_order_list')

    order.approved = True
    order.approved_at = timezone.now()
    order.save()
    messages.success(request, "Purchase order approved.")
    return redirect('procurement:purchase_order_list')


@login_required
@procurement_permission_required("procurement_orders_edit")
def purchase_order_edit(request, order_id):
    order = get_object_or_404(
        PurchaseOrder,
        id=order_id,
        deleted_at__isnull=True,
    )
    if order.approved:
        return HttpResponseForbidden("Approved purchase orders cannot be edited.")
    if order.quotation_id:
        return HttpResponseForbidden("Orders based on accepted supplier quotations cannot be edited.")
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, instance=order)
        formset = PurchaseOrderItemFormSet(request.POST, instance=order)
        if form.is_valid() and formset.is_valid():
            order_total = sum(
                (
                    item_form.cleaned_data["quantity"]
                    * item_form.cleaned_data["unit_price"]
                    for item_form in formset.forms
                    if item_form.cleaned_data.get("description")
                    and not item_form.cleaned_data.get("DELETE", False)
                ),
                start=0,
            )
            if (
                order.requisition_id
                and order.requisition.total_amount > 0
                and order_total > order.requisition.total_amount
            ):
                form.add_error(
                    "requisition",
                    "The purchase order cannot exceed the approved requisition amount.",
                )
                return render(
                    request,
                    "procurement/purchase_order_add.html",
                    {"form": form, "formset": formset, "order": order},
                )
            with transaction.atomic():
                form.save()
                formset.save()
                order.total_amount = order.items_total
                order.save(update_fields=["total_amount", "updated_at"])
            return redirect("procurement:purchase_order_list")
    else:
        form = PurchaseOrderForm(instance=order)
        formset = PurchaseOrderItemFormSet(instance=order)
    return render(request, "procurement/purchase_order_add.html", {"form": form, "formset": formset, "order": order})


@login_required
@require_POST
@procurement_permission_required("procurement_orders_delete")
def purchase_order_delete(request, order_id):
    order = get_object_or_404(
        PurchaseOrder,
        id=order_id,
        deleted_at__isnull=True,
    )
    if order.approved:
        return HttpResponseForbidden("Approved purchase orders cannot be deleted.")
    order.soft_delete()
    messages.success(request, "Purchase order deleted.")
    return redirect("procurement:purchase_order_list")


@login_required
@procurement_permission_required("procurement_orders")
def purchase_order_detail(request, order_id):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related(
            'supplier',
            'requisition',
            'quotation',
        ).prefetch_related('items'),
        id=order_id,
        deleted_at__isnull=True,
    )
    return render(request, 'procurement/purchase_order_detail.html', {'order': order})


@login_required
@procurement_permission_required("procurement_orders")
def purchase_order_print(request, order_id):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related(
            'supplier',
            'requisition',
            'quotation',
        ).prefetch_related('items'),
        id=order_id,
        deleted_at__isnull=True,
    )
    return render(request, 'procurement/purchase_order_print.html', {'order': order})


@login_required
@procurement_permission_required("procurement_quotations", "procurement_requisitions")
def purchase_quotation_list(request):
    quotations = PurchaseQuotation.objects.filter(
        deleted_at__isnull=True,
    ).select_related("supplier", "requisition")
    return render(
        request,
        "procurement/purchase_quotation_list.html",
        {"quotations": quotations},
    )


@login_required
@procurement_permission_required("procurement_quotations_add", "procurement_requisitions_add")
def purchase_quotation_add(request):
    quotation = PurchaseQuotation()
    if request.method == "POST":
        form = PurchaseQuotationForm(request.POST, request.FILES)
        formset = PurchaseQuotationItemFormSet(request.POST, instance=quotation)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                quotation = form.save(commit=False)
                quotation.created_by = request.user
                quotation.save()
                formset.instance = quotation
                formset.save()
                quotation.total_amount = quotation.items_total
                quotation.save(update_fields=["total_amount", "updated_at"])
            messages.success(request, "Supplier quotation recorded.")
            return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    else:
        form = PurchaseQuotationForm()
        formset = PurchaseQuotationItemFormSet(instance=quotation)
    return render(
        request,
        "procurement/purchase_quotation_add.html",
        {"form": form, "formset": formset},
    )


@login_required
@procurement_permission_required("procurement_quotations", "procurement_requisitions")
def purchase_quotation_detail(request, quotation_id):
    quotation = get_object_or_404(
        PurchaseQuotation.objects.select_related(
            "supplier",
            "requisition",
            "created_by",
        ).prefetch_related("items"),
        pk=quotation_id,
        deleted_at__isnull=True,
    )
    return render(
        request,
        "procurement/purchase_quotation_detail.html",
        {
            "quotation": quotation,
            "status_choices": _quotation_transitions(quotation),
        },
    )


@login_required
@procurement_permission_required("procurement_quotations", "procurement_requisitions")
def purchase_quotation_print(request, quotation_id):
    quotation = get_object_or_404(
        PurchaseQuotation.objects.select_related(
            "supplier",
            "requisition",
        ).prefetch_related("items"),
        pk=quotation_id,
        deleted_at__isnull=True,
    )
    if not quotation.document:
        messages.error(request, "No supplier quotation document is attached.")
        return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    filename = Path(quotation.document.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(
        quotation.document.open("rb"),
        as_attachment=False,
        filename=filename,
        content_type=content_type,
    )


@login_required
@require_POST
@procurement_permission_required("procurement_quotations_edit", "procurement_requisitions_edit")
def purchase_quotation_change_status(request, quotation_id):
    quotation = get_object_or_404(
        PurchaseQuotation,
        pk=quotation_id,
        deleted_at__isnull=True,
    )
    status = request.POST.get("status")
    valid_statuses = {choice for choice, _label in _quotation_transitions(quotation)}
    if status not in valid_statuses:
        messages.error(request, "Select a valid supplier quotation status.")
        return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    if status == PurchaseQuotation.Status.ACCEPTED and (
        not quotation.requisition_id
        or not quotation.requisition.status
        or quotation.requisition.status.slug != "approved"
    ):
        messages.error(request, "A quotation can only be selected for an approved requisition.")
        return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    if status == PurchaseQuotation.Status.ACCEPTED and (
        quotation.valid_until and quotation.valid_until < timezone.localdate()
    ):
        messages.error(request, "An expired quotation cannot be accepted.")
        return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    if status == PurchaseQuotation.Status.ACCEPTED and quotation.total_amount <= 0:
        messages.error(request, "A quotation must have a positive total before it can be selected.")
        return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    if status == PurchaseQuotation.Status.ACCEPTED and not quotation.document:
        messages.error(request, "Attach the supplier's original quotation before selecting the offer.")
        return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    if status == PurchaseQuotation.Status.ACCEPTED and (
        not quotation.items.exists()
        or quotation.items_total != quotation.total_amount
    ):
        messages.error(request, "The quotation must have complete line items before it can be selected.")
        return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    if status == PurchaseQuotation.Status.ACCEPTED and (
        quotation.requisition.total_amount > 0
        and quotation.total_amount > quotation.requisition.total_amount
    ):
        messages.error(request, "The quotation exceeds the approved requisition amount.")
        return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
    with transaction.atomic():
        quotation = PurchaseQuotation.objects.select_for_update().get(pk=quotation.pk)
        if status == PurchaseQuotation.Status.ACCEPTED:
            requisition = PurchaseRequisition.objects.select_for_update().get(
                pk=quotation.requisition_id
            )
            if (
                requisition.deleted_at is not None
                or not requisition.status
                or requisition.status.slug != "approved"
            ):
                messages.error(request, "The linked requisition is no longer approved.")
                return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
            already_selected = PurchaseQuotation.objects.filter(
                requisition_id=quotation.requisition_id,
                status=PurchaseQuotation.Status.ACCEPTED,
                deleted_at__isnull=True,
            ).exclude(pk=quotation.pk)
            if already_selected.exists():
                messages.error(request, "Another quotation has already been selected for this requisition.")
                return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
            if quotation.purchase_orders.filter(deleted_at__isnull=True).exists():
                messages.error(request, "A quotation linked to a purchase order cannot be changed.")
                return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)
        quotation.status = status
        quotation.save(update_fields=["status", "updated_at"])
    messages.success(request, "Supplier quotation status updated.")
    return redirect("procurement:purchase_quotation_detail", quotation_id=quotation.pk)


def _quotation_transitions(quotation):
    if quotation.status == PurchaseQuotation.Status.RECEIVED:
        statuses = (PurchaseQuotation.Status.UNDER_REVIEW,)
    elif quotation.status == PurchaseQuotation.Status.UNDER_REVIEW:
        statuses = (
            PurchaseQuotation.Status.ACCEPTED,
            PurchaseQuotation.Status.DECLINED,
        )
    else:
        statuses = ()
    labels = dict(PurchaseQuotation.Status.choices)
    return [(status, labels[status]) for status in statuses]


@login_required
@procurement_permission_required("procurement_orders_export")
def export_purchase_order_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="purchase_orders.csv"'
    writer = csv.writer(response)
    writer.writerow(['Supplier', 'Requisition', 'Order Date', 'Total Amount', 'Approved'])

    for order in PurchaseOrder.objects.filter(deleted_at__isnull=True).select_related('supplier', 'requisition'):
        writer.writerow([
            order.supplier.name,
            order.requisition.title if order.requisition else '',
            order.order_date,
            order.total_amount,
            'Yes' if order.approved else 'No',
        ])
    return response


@login_required
@procurement_permission_required("procurement_orders_export")
def export_purchase_order_excel(request):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Purchase Orders"
    worksheet.append(["Supplier", "Requisition", "Order Date", "Total Amount", "Approved"])
    orders = PurchaseOrder.objects.filter(
        deleted_at__isnull=True,
    ).select_related("supplier", "requisition")
    for order in orders:
        worksheet.append(
            [
                order.supplier.name,
                order.requisition.title if order.requisition else "",
                order.order_date,
                order.total_amount,
                "Yes" if order.approved else "No",
            ]
        )
    output = BytesIO()
    workbook.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="purchase_orders.xlsx"'
    return response


@login_required
@procurement_permission_required("procurement_orders_add")
def purchase_order_add(request):
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.approved = False
            order.approved_at = None
            quotation = form.cleaned_data["quotation"]
            if (
                quotation.requisition.total_amount > 0
                and quotation.total_amount > quotation.requisition.total_amount
            ):
                form.add_error(
                    "quotation",
                    "The accepted quotation exceeds the approved requisition amount.",
                )
            elif (
                not quotation.items.exists()
                or quotation.items_total != quotation.total_amount
            ):
                form.add_error(
                    "quotation",
                    "The accepted quotation has incomplete or inconsistent line items.",
                )
            else:
                with transaction.atomic():
                    order.total_amount = quotation.total_amount
                    order.save()
                    PurchaseOrderItem.objects.bulk_create(
                        [
                            PurchaseOrderItem(
                                purchase_order=order,
                                description=item.description,
                                quantity=item.quantity,
                                unit_price=item.unit_price,
                            )
                            for item in quotation.items.all()
                        ]
                    )
                return redirect("procurement:purchase_order_list")
    else:
        form = PurchaseOrderForm()

    return render(request, "procurement/purchase_order_add.html", {"form": form})
