from django.db import migrations


PERMISSIONS = (
    ("view_students", "View student records"),
    ("manage_students", "Create and update student records"),
    ("manage_documents", "Upload student documents"),
    ("view_documents", "View student documents"),
    ("export_students", "Export student records"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for action, name in PERMISSIONS:
        permission, _created = Permission.objects.get_or_create(
            module="students",
            action=action,
            defaults={"name": name, "code": f"students.{action}"},
        )
        if permission.code != f"students.{action}":
            permission.code = f"students.{action}"
            permission.save(update_fields=("code",))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0020_student_lifecycle_documents"),
    ]

    operations = [
        migrations.RunPython(seed_permissions, migrations.RunPython.noop),
    ]
