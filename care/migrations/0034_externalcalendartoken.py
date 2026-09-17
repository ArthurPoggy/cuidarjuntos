# Card #49 -- credenciais de calendarios externos conectados.
#
# Depende de 0033_usuario_varios_grupos (card #38) e nao diretamente da
# merge canonica 0032_merge_0030_0031: duas migrations irmas em 0033
# criariam de novo dois leaf nodes no grafo, quebrando o `migrate` de quem
# mesclasse os dois PRs. Por isso o lote de calendario e empilhado sobre o
# #38, formando uma sequencia unica.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_cryptography.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("care", "0033_usuario_varios_grupos"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalCalendarToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("google", "Google Calendar"),
                            ("microsoft", "Microsoft Outlook"),
                        ],
                        max_length=20,
                        verbose_name="Provedor",
                    ),
                ),
                (
                    "access_token",
                    django_cryptography.fields.encrypt(
                        models.TextField(
                            blank=True, default="", verbose_name="Access token"
                        )
                    ),
                ),
                (
                    "refresh_token",
                    django_cryptography.fields.encrypt(
                        models.TextField(
                            blank=True, default="", verbose_name="Refresh token"
                        )
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Escopo concedido",
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Expira em"
                    ),
                ),
                (
                    "account_email",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Email da conta",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Ativo")),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Criado em"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Atualizado em"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="external_calendar_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Token de calendário externo",
                "verbose_name_plural": "Tokens de calendário externo",
            },
        ),
        migrations.AddConstraint(
            model_name="externalcalendartoken",
            constraint=models.UniqueConstraint(
                fields=("user", "provider"),
                name="unique_external_calendar_token_per_user_provider",
            ),
        ),
    ]
