from django.db import migrations


def noop(apps, schema_editor):
    # No DB changes required; business validation disabled at model clean level
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(noop, reverse_code=noop),
    ]

