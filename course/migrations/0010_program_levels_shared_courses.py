import collections

import django.db.models.deletion
from django.db import migrations, models


def migrate_program_academics(apps, schema_editor):
    AcademicYear = apps.get_model("course", "AcademicYear")
    Course = apps.get_model("course", "Course")
    Program = apps.get_model("course", "Program")
    ProgramLevel = apps.get_model("course", "ProgramLevel")
    database = schema_editor.connection.alias

    level_names = set(
        Course.objects.using(database)
        .exclude(level__isnull=True)
        .exclude(level="")
        .values_list("level", flat=True)
    )
    level_names.update(("Bachelor", "Master"))
    levels = {
        name: ProgramLevel.objects.using(database).get_or_create(name=name)[0]
        for name in level_names
    }

    year_numbers = set(
        Course.objects.using(database).values_list("year", flat=True)
    )
    year_numbers.update(range(1, 7))
    AcademicYear.objects.using(database).bulk_create(
        [AcademicYear(number=number) for number in sorted(year_numbers)],
        ignore_conflicts=True,
    )

    level_counts = collections.defaultdict(collections.Counter)
    through = Course._meta.get_field("programs").remote_field.through
    for course in Course.objects.using(database).all().iterator():
        if course.program_id:
            through.objects.using(database).get_or_create(
                course_id=course.pk,
                program_id=course.program_id,
            )
            if course.level in levels:
                level_counts[course.program_id][course.level] += 1

    for program_id, counts in level_counts.items():
        most_common_level = sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]
        Program.objects.using(database).filter(pk=program_id).update(
            level_id=levels[most_common_level].pk
        )


class Migration(migrations.Migration):

    dependencies = [
        ("course", "0009_program_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicYear",
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
                ("number", models.PositiveSmallIntegerField(unique=True)),
            ],
            options={"ordering": ("number",)},
        ),
        migrations.CreateModel(
            name="ProgramLevel",
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
                ("name", models.CharField(max_length=50, unique=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.AddField(
            model_name="program",
            name="level",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="programs",
                to="course.programlevel",
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="programs",
            field=models.ManyToManyField(
                related_name="courses",
                to="course.program",
            ),
        ),
        migrations.RunPython(migrate_program_academics, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="course",
            name="level",
        ),
        migrations.RemoveField(
            model_name="course",
            name="program",
        ),
        migrations.AlterField(
            model_name="course",
            name="year",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
