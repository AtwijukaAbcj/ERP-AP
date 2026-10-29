from django.db import migrations


def seed_reporting_permission(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.get_or_create(
        module="reports",
        action="view",
        defaults={
            "name": "View institutional reports",
            "code": "reports.view",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_seed_student_management_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_reporting_permission, migrations.RunPython.noop),
    ]
