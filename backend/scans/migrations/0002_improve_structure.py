# Generated manually for structure improvements

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scans", "0001_initial"),
    ]

    operations = [
        # Add new fields to Scan
        migrations.AddField(
            model_name="scan",
            name="internal_urls",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="scan",
            name="external_urls",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="scan",
            name="hidden_urls",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="scan",
            name="error_urls",
            field=models.IntegerField(default=0),
        ),
        # Add external_domain field to DiscoveredURL
        migrations.AddField(
            model_name="discoveredurl",
            name="external_domain",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="For external URLs, the domain they point to",
                max_length=255,
            ),
        ),
        # Add index on is_internal
        migrations.AlterField(
            model_name="discoveredurl",
            name="is_internal",
            field=models.BooleanField(db_index=True, default=True),
        ),
        # Add new indexes
        migrations.AddIndex(
            model_name="discoveredurl",
            index=models.Index(
                fields=["scan", "is_internal"],
                name="scans_disco_scan_id_intern_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="discoveredurl",
            index=models.Index(
                fields=["scan", "status_code"],
                name="scans_disco_scan_id_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="discoveredurl",
            index=models.Index(
                fields=["scan", "external_domain"],
                name="scans_disco_scan_id_extdom_idx",
            ),
        ),
    ]
