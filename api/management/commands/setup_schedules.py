import json

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from care.models import CareGroup


class Command(BaseCommand):
    """Configura (de forma idempotente) o agendamento do relatório semanal.

    Cria/atualiza um único `CrontabSchedule` (toda segunda-feira às 08h,
    fuso America/Sao_Paulo) e, para cada `CareGroup` existente, um
    `PeriodicTask` apontando para `api.tasks.send_weekly_report` com
    `args=[group_id]`.

    Rodar o comando novamente é seguro: grupos já agendados apenas têm seu
    `PeriodicTask` atualizado (não duplicado), e novos grupos criados desde a
    última execução ganham seu próprio `PeriodicTask`.
    """

    help = (
        "Cria/atualiza o CrontabSchedule (segunda-feira 08h, "
        "America/Sao_Paulo) e um PeriodicTask por grupo apontando para "
        "api.tasks.send_weekly_report."
    )

    def handle(self, *args, **options):
        schedule, schedule_created = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="8",
            day_of_week="1",
            day_of_month="*",
            month_of_year="*",
            timezone="America/Sao_Paulo",
        )

        created_count = 0
        updated_count = 0

        for group in CareGroup.objects.all():
            task_name = f"send-weekly-report-group-{group.pk}"
            _, created = PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "crontab": schedule,
                    "interval": None,
                    "task": "api.tasks.send_weekly_report",
                    "args": json.dumps([group.pk]),
                    "enabled": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "CrontabSchedule %s (id=%s): %d PeriodicTask(s) criada(s), "
                "%d atualizada(s)."
                % (
                    "criado" if schedule_created else "já existia",
                    schedule.pk,
                    created_count,
                    updated_count,
                )
            )
        )
