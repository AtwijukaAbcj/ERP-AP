import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils.translation import gettext_lazy as _
import accounts.models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0019_alter_permission_unique_together_permission_action_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="student",
            name="cohort",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="student",
            name="admission_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="student",
            name="expected_completion_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="student",
            name="next_of_kin_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="student",
            name="next_of_kin_phone",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="student",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", _("Active")),
                    ("on_leave", _("On leave")),
                    ("suspended", _("Suspended")),
                    ("graduated", _("Graduated")),
                    ("withdrawn", _("Withdrawn")),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="StudentDocument",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("identification", _("Identification")),
                            ("academic", _("Academic record")),
                            ("medical", _("Medical")),
                            ("financial", _("Financial")),
                            ("other", _("Other")),
                        ],
                        max_length=30,
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                (
                    "file",
                    models.FileField(
                        storage=accounts.models.student_document_storage,
                        upload_to="student_documents/%Y/%m/",
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                ["pdf", "jpg", "jpeg", "png"]
                            )
                        ],
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="accounts.student",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_student_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-uploaded_at",)},
        ),
        migrations.CreateModel(
            name="StudentStatusHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "from_status",
                    models.CharField(
                        choices=[
                            ("active", _("Active")),
                            ("on_leave", _("On leave")),
                            ("suspended", _("Suspended")),
                            ("graduated", _("Graduated")),
                            ("withdrawn", _("Withdrawn")),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "to_status",
                    models.CharField(
                        choices=[
                            ("active", _("Active")),
                            ("on_leave", _("On leave")),
                            ("suspended", _("Suspended")),
                            ("graduated", _("Graduated")),
                            ("withdrawn", _("Withdrawn")),
                        ],
                        max_length=20,
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="student_status_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="accounts.student",
                    ),
                ),
            ],
            options={"ordering": ("-changed_at",)},
        ),
    ]
