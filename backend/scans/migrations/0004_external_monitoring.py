"""Migration for External Domain Monitoring system."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("scans", "0003_rename_scans_disco_scan_id_5a2fd6_idx_scans_disco_scan_id_857bce_idx_and_more"),
    ]

    operations = [
        # Add source_url field to DiscoveredURL
        migrations.AddField(
            model_name="discoveredurl",
            name="source_url",
            field=models.URLField(
                blank=True, default="", max_length=2048,
                help_text="The page where this URL was discovered",
            ),
        ),

        # Create ExternalDomainEntry table
        migrations.CreateModel(
            name="ExternalDomainEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_domain", models.CharField(db_index=True, max_length=255)),
                ("domain", models.CharField(db_index=True, max_length=255)),
                ("status", models.CharField(
                    choices=[("safe", "Safe"), ("suspicious", "Suspicious"), ("new", "New")],
                    default="new", max_length=20,
                )),
                ("is_suspicious", models.BooleanField(default=False)),
                ("suspicious_reasons", models.JSONField(blank=True, default=list)),
                ("first_seen", models.DateTimeField(auto_now_add=True)),
                ("last_seen", models.DateTimeField(auto_now=True)),
                ("times_seen", models.IntegerField(default=1)),
                ("found_on_pages", models.JSONField(blank=True, default=list)),
                ("first_seen_scan", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="first_seen_domains", to="scans.scan",
                )),
                ("last_seen_scan", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="last_seen_domains", to="scans.scan",
                )),
            ],
            options={
                "ordering": ["-last_seen"],
                "unique_together": {("site_domain", "domain")},
                "indexes": [
                    models.Index(fields=["site_domain", "is_suspicious"], name="scans_exter_site_do_susp_idx"),
                    models.Index(fields=["site_domain", "status"], name="scans_exter_site_do_stat_idx"),
                ],
            },
        ),

        # Create ExternalDomainAlert table
        migrations.CreateModel(
            name="ExternalDomainAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_domain", models.CharField(db_index=True, max_length=255)),
                ("external_domain", models.CharField(max_length=255)),
                ("alert_type", models.CharField(
                    choices=[
                        ("new_domain", "New External Domain"),
                        ("suspicious_domain", "Suspicious Domain"),
                        ("removed_domain", "Domain Removed"),
                    ],
                    max_length=30,
                )),
                ("severity", models.CharField(
                    choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")],
                    default="info", max_length=10,
                )),
                ("message", models.TextField()),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("scan", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="alerts", to="scans.scan",
                )),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["site_domain", "-created_at"], name="scans_alert_site_date_idx"),
                    models.Index(fields=["is_read"], name="scans_alert_is_read_idx"),
                ],
            },
        ),
    ]
