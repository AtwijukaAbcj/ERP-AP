import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
        ("result", "0004_takencourse_safe_drops"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="takencourse",
            name="unique_active_student_course",
        ),
        migrations.AddField(
            model_name="takencourse",
            name="semester",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="course_enrollments",
                to="core.semester",
            ),
        ),
        migrations.AddField(
            model_name="takencourse",
            name="dropped_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="takencourse",
            name="dropped_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dropped_course_enrollments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="takencourse",
            constraint=models.UniqueConstraint(
                condition=Q(is_dropped=False, semester__isnull=False),
                fields=("student", "course", "semester"),
                name="unique_active_student_course_semester",
            ),
        ),
    ]
