from django.db import migrations, models


def copy_primary_roles_to_role_assignments(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    role_assignments = User.roles.through
    assignments = (
        role_assignments(user_id=user_id, role_id=role_id)
        for user_id, role_id in User.objects.exclude(role__isnull=True).values_list(
            "id", "role_id"
        )
    )
    role_assignments.objects.bulk_create(assignments, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0027_alter_modulepermission_module_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="roles",
            field=models.ManyToManyField(
                blank=True,
                related_name="users",
                to="accounts.role",
            ),
        ),
        migrations.RunPython(
            copy_primary_roles_to_role_assignments,
            migrations.RunPython.noop,
        ),
    ]
