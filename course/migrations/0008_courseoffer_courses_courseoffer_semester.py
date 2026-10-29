import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_newsandevents_event_date_newsandevents_semester_and_more"),
        ("course", "0007_program_faculty"),
    ]

    operations = [
        migrations.AddField(
            model_name="courseoffer",
            name="courses",
            field=models.ManyToManyField(
                blank=True,
                related_name="course_offers",
                to="course.course",
            ),
        ),
        migrations.AddField(
            model_name="courseoffer",
            name="semester",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="course_offers",
                to="core.semester",
            ),
        ),
    ]
