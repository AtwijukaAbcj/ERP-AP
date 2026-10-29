import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0021_seed_student_management_permissions"),
        ("core", "0007_remove_newsandevents_summary_en_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Ward",
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
                ("name", models.CharField(max_length=150)),
                (
                    "facility",
                    models.CharField(default="Butabika Hospital", max_length=200),
                ),
                ("description", models.TextField(blank=True)),
                ("capacity", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("facility", "name")},
        ),
        migrations.CreateModel(
            name="ClinicalPlacement",
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
                    "starts_on",
                    models.DateField(),
                ),
                ("ends_on", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("planned", "Planned"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="planned",
                        max_length=20,
                    ),
                ),
                ("learning_objectives", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_clinical_placements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "semester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="clinical_placements",
                        to="core.semester",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="clinical_placements",
                        to="accounts.student",
                    ),
                ),
                (
                    "supervisor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="supervised_clinical_placements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "ward",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="placements",
                        to="clinical.ward",
                    ),
                ),
            ],
            options={"ordering": ("-starts_on", "student__registration_number")},
        ),
        migrations.CreateModel(
            name="PlacementStatusHistory",
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
                            ("planned", "Planned"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "to_status",
                    models.CharField(
                        choices=[
                            ("planned", "Planned"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
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
                        related_name="clinical_placement_status_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "placement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="clinical.clinicalplacement",
                    ),
                ),
            ],
            options={"ordering": ("-changed_at",)},
        ),
        migrations.CreateModel(
            name="ClinicalLogEntry",
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
                ("date", models.DateField()),
                (
                    "shift",
                    models.CharField(
                        choices=[
                            ("day", "Day"),
                            ("evening", "Evening"),
                            ("night", "Night"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "hours",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=4,
                        validators=[
                            django.core.validators.MinValueValidator(0.25),
                            django.core.validators.MaxValueValidator(24),
                        ],
                    ),
                ),
                ("competency", models.CharField(max_length=200)),
                ("activity", models.TextField()),
                ("reflection", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending review"),
                            ("verified", "Verified"),
                            ("returned", "Returned to student"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=12,
                    ),
                ),
                ("supervisor_feedback", models.TextField(blank=True)),
                (
                    "submitted_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "placement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="log_entries",
                        to="clinical.clinicalplacement",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_clinical_log_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-date", "-submitted_at")},
        ),
        migrations.AddConstraint(
            model_name="ward",
            constraint=models.UniqueConstraint(
                fields=("facility", "name"),
                name="unique_clinical_ward_per_facility",
            ),
        ),
        migrations.AddIndex(
            model_name="clinicalplacement",
            index=models.Index(
                fields=["ward", "status", "starts_on", "ends_on"],
                name="clinical_cl_ward_i_2b1360_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="clinicalplacement",
            index=models.Index(
                fields=["student", "status"],
                name="clinical_cl_student_c6a5f4_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="clinicallogentry",
            index=models.Index(
                fields=["placement", "status", "date"],
                name="clinical_cl_placeme_1396fc_idx",
            ),
        ),
    ]
