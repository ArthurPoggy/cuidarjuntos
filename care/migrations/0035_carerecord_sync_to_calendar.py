# Card #41 -- os dois campos de sincronizacao do CareRecord.
#
# `sync_to_calendar` e a escolha do usuario no formulario; 
# `synced_to_external_at` e o controle de idempotencia da task diaria
# (card #45). Sao o par natural e vem juntos aqui: separa-los em duas
# migrations, uma por PR, daria AddField duplicado do mesmo campo ao
# mesclar os dois.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("care", "0034_externalcalendartoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="carerecord",
            name="sync_to_calendar",
            field=models.BooleanField(
                default=False, verbose_name="Sincronizar com calendário externo"
            ),
        ),
        migrations.AddField(
            model_name="carerecord",
            name="synced_to_external_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Sincronizado com calendário externo em",
            ),
        ),
    ]
