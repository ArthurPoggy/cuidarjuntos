from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("care", "0013_carerecord_missed_reason"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Medication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, verbose_name="Nome")),
                ("dosage", models.CharField(max_length=50, verbose_name="Dosagem")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="medications_created", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="medications", to="care.caregroup")),
            ],
            options={
                "ordering": ["name", "dosage"],
                "constraints": [
                    models.UniqueConstraint(fields=("group", "name", "dosage"), name="unique_medication_per_group"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MedicationStockEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(verbose_name="Quantidade de cápsulas")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="medication_stock_entries", to=settings.AUTH_USER_MODEL)),
                ("medication", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_entries", to="care.medication")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="carerecord",
            name="medication",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="care_records", to="care.medication"),
        ),
        migrations.AddField(
            model_name="carerecord",
            name="capsule_quantity",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Quantidade de cápsulas"),
        ),
    ]
