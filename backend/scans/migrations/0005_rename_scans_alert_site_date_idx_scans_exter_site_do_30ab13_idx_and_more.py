# Compatibility migration for historical index-rename branch.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("scans", "0004_external_monitoring"),
    ]

    operations = []
