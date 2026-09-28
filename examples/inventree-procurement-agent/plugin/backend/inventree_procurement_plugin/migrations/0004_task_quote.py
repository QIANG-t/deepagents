"""Store one immutable, source-backed quote extraction per task."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventree_procurement_plugin", "0003_task_explanation")]

    operations = [
        migrations.AddField(model_name="procurementtask", name="quote", field=models.JSONField(default=dict)),
        migrations.AddField(model_name="procurementtask", name="quote_started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="procurementtask", name="quote_run_id", field=models.UUIDField(blank=True, null=True)),
    ]
