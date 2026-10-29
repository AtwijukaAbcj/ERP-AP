from django.db import migrations


PERMISSIONS = (
    ("view_applications", "View admission applications"),
    ("manage_applications", "Create and edit admission applications"),
    ("review_applications", "Review admission applications"),
    ("link_students", "Link accepted applicants to student records"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for action, name in PERMISSIONS:
        permission, _created = Permission.objects.get_or_create(
            module="admissions",
            action=action,
            defaults={
                "name": name,
                "code": f"admissions.{action}",
            },
        )
        if permission.code != f"admissions.{action}":
            permission.code = f"admissions.{action}"
            permission.save(update_fields=("code",))


class Migration(migrations.Migration):
    dependencies = [
        ("admissions", "0001_initial"),
        ("accounts", "0019_alter_permission_unique_together_permission_action_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_permissions, migrations.RunPython.noop),
    ]
