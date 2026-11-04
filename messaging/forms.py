from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from accounts.models import Role
from .recipients import ACCOUNT_CATEGORIES, can_send_group_messages, resolve_recipients

User = get_user_model()


class ComposeMessageForm(forms.Form):
    RECIPIENT_TYPES = (
        ("individual", _("Specific people")),
        ("role", _("Custom user role")),
        ("category", _("Account category")),
    )

    recipient_type = forms.ChoiceField(
        choices=RECIPIENT_TYPES,
        initial="individual",
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Send to"),
    )
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 8}),
        label=_("People"),
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "searchable-checkbox-input"}
        ),
        label=_("Roles"),
    )
    categories = forms.MultipleChoiceField(
        choices=ACCOUNT_CATEGORIES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Account categories"),
    )
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Subject"),
    )
    body = forms.CharField(
        max_length=10000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        label=_("Message"),
    )

    def __init__(self, sender, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender = sender
        self.can_send_groups = can_send_group_messages(sender)
        self.fields["users"].queryset = (
            User.objects.filter(is_active=True)
            .exclude(pk=sender.pk)
            .order_by("last_name", "first_name", "username")
        )
        self.fields["roles"].queryset = Role.objects.order_by("name")
        if not self.can_send_groups:
            self.fields["recipient_type"].choices = (self.RECIPIENT_TYPES[0],)

    def clean(self):
        cleaned_data = super().clean()
        recipient_type = cleaned_data.get("recipient_type")
        users = cleaned_data.get("users")
        roles = cleaned_data.get("roles")
        categories = cleaned_data.get("categories")
        if recipient_type == "individual" and not users:
            self.add_error("users", _("Choose at least one recipient."))
        elif recipient_type == "role" and not roles:
            self.add_error("roles", _("Choose at least one role."))
        elif recipient_type == "category" and not categories:
            self.add_error("categories", _("Choose at least one account category."))

        if recipient_type in {"role", "category"} and not self.can_send_groups:
            self.add_error(
                "recipient_type",
                _("Only staff members can message roles or account categories."),
            )

        if recipient_type in {"role", "category"} or (
            recipient_type == "individual" and users and users.count() > 1
        ):
            if not cleaned_data.get("subject"):
                self.add_error("subject", _("A subject is required for group messages."))

        if recipient_type and not any(
            name in self.errors for name in ("recipient_type", "users", "roles", "categories")
        ):
            recipients = resolve_recipients(
                self.sender,
                recipient_type,
                users=users,
                roles=roles,
                categories=categories,
            )
            if not recipients.exists():
                self.add_error(
                    None,
                    _("There are no active recipients for the selected target."),
                )
        return cleaned_data

    def get_recipients(self):
        return resolve_recipients(
            self.sender,
            self.cleaned_data["recipient_type"],
            users=self.cleaned_data.get("users"),
            roles=self.cleaned_data.get("roles"),
            categories=self.cleaned_data.get("categories"),
        )
