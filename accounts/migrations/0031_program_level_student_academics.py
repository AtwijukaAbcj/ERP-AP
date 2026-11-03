from django.db import migrations, models


def align_student_levels(apps, schema_editor):
    Student = apps.get_model("accounts", "Student")
    database = schema_editor.connection.alias
    students = (
        Student.objects.using(database)
        .filter(program__level__isnull=False)
        .values_list("pk", "program__level__name")
    )
    for student_id, level_name in students.iterator():
        Student.objects.using(database).filter(pk=student_id).update(
            level=level_name
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0030_user_last_activity"),
        ("course", "0010_program_levels_shared_courses"),
    ]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="level",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="student",
            name="year",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(align_student_levels, migrations.RunPython.noop),
    ]
