from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("care", "0009_alter_carerecord_series_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="caregroup",
            name="join_code_hash",
            field=models.CharField(blank=True, default="", max_length=128, verbose_name="Senha do grupo"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="carerecord",
            name="is_exception",
            field=models.BooleanField(db_index=True, default=False, verbose_name="É exceção"),
        ),
        migrations.AddField(
            model_name="carerecord",
            name="progress_trend",
            field=models.CharField(
                blank=True,
                choices=[("evolution", "Evolução"), ("regression", "Regressão")],
                default="",
                max_length=12,
                verbose_name="Evolução ou Regressão",
            ),
            preserve_default=False,
        ),
    ]
