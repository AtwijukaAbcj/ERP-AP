from django.db import migrations


def seed_fee_category_action_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    actions = (
        ("fee_category.add", "Add fee categories"),
        ("fee_category.edit", "Edit fee categories"),
        ("fee_category.delete", "Delete fee categories"),
    )
    for action, name in actions:
        Permission.objects.get_or_create(
            module="finance",
            action=action,
            defaults={
                "name": name,
                "code": f"finance.{action}",
                "description": f"Allows a user to {name.lower()}.",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_seed_reporting_permission"),
        ("finance", "0012_alter_invoicepayment_method_onlineinvoicepayment"),
    ]

    operations = [
        migrations.RunPython(
            seed_fee_category_action_permissions,
            migrations.RunPython.noop,
        ),
    ]
