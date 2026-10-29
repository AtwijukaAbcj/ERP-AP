from django.db import migrations


PERMISSIONS = (
    ("view_placements", "View clinical placements"),
    ("manage_placements", "Create and manage clinical placements and wards"),
    ("verify_log_entries", "Review and verify clinical log entries"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for action, name in PERMISSIONS:
        Permission.objects.get_or_create(
            module="clinical",
            action=action,
            defaults={"name": name, "code": f"clinical.{action}"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_seed_student_management_permissions"),
        ("clinical", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_permissions, migrations.RunPython.noop),
    ]
