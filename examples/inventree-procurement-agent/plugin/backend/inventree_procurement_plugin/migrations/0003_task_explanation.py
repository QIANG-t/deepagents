"""Cache successful AI explanations and coordinate generation."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventree_procurement_plugin", "0002_task_preview")]

    operations = [
        migrations.AddField(model_name="procurementtask", name="explanation", field=models.JSONField(default=dict)),
        migrations.AddField(model_name="procurementtask", name="explanation_started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="procurementtask", name="explanation_run_id", field=models.UUIDField(blank=True, null=True)),
    ]
