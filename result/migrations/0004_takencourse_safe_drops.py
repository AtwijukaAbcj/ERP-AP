from django.db import migrations, models
from django.db.models import Count, Q
import result.models


def reject_duplicate_active_enrollments(apps, schema_editor):
    TakenCourse = apps.get_model("result", "TakenCourse")
    duplicates = (
        TakenCourse.objects.values("student_id", "course_id")
        .annotate(enrollment_count=Count("id"))
        .filter(enrollment_count__gt=1)
    )
    if duplicates.exists():
        raise RuntimeError(
            "Cannot add the active enrollment constraint: duplicate student/course "
            "records exist. Resolve them without deleting grade data, then retry."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("result", "0003_assessmentconfig_courseassignment_attendancerecord_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="takencourse",
            name="is_dropped",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RunPython(
            reject_duplicate_active_enrollments,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="takencourse",
            constraint=models.UniqueConstraint(
                fields=("student", "course"),
                condition=Q(is_dropped=False),
                name="unique_active_student_course",
            ),
        ),
        migrations.AlterModelManagers(
            name="takencourse",
            managers=[
                ("objects", result.models.ActiveTakenCourseManager()),
            ],
        ),
    ]
