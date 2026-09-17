# Merge migration canonica: resolve os dois leaf nodes que existiam em
# `desenvolvimento` (0030_carerecord_photo e 0031_groupmembership_
# receive_weekly_report). Nome deterministico (sem timestamp) para que
# todos os PRs do lote apontem para o MESMO arquivo em vez de cada um
# criar a sua propria merge migration com um timestamp diferente.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("care", "0030_carerecord_photo"),
        ("care", "0031_groupmembership_receive_weekly_report"),
    ]

    operations = []
