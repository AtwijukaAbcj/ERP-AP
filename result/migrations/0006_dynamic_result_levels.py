from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course", "0010_program_levels_shared_courses"),
        ("result", "0005_takencourse_drop_audit_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="result",
            name="level",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
