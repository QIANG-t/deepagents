"""Persist the read-only factual preview for restart recovery."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventree_procurement_plugin", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="procurementtask",
            name="preview",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="procurementtask",
            name="analyzed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
