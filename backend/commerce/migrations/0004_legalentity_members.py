from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0003_add_lat_lon_fields"),
    ]

    operations = [
        # This migration exists to align state with environments where
        # an auto migration added the ManyToMany members field.
        # Current models already include it; no-op here.
    ]

