import json

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from care.models import CareGroup, GroupMembership, Patient
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class SetupSchedulesCommandTests(TestCase):
    """Testes do management command `setup_schedules`."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass")
        self.patient1 = Patient.objects.create(name="Vovó")
        self.patient2 = Patient.objects.create(name="Vovô")
        self.group1 = CareGroup.objects.create(name="Família 1", patient=self.patient1)
        self.group2 = CareGroup.objects.create(name="Família 2", patient=self.patient2)
        GroupMembership.objects.create(
            user=self.user, group=self.group1, relation_to_patient="FAMILY"
        )

    def test_creates_crontab_schedule_monday_8am_sao_paulo(self):
        """Cria um CrontabSchedule para segunda-feira às 08h, America/Sao_Paulo."""
        call_command("setup_schedules")

        schedules = CrontabSchedule.objects.filter(
            hour="8", minute="0", day_of_week="1", timezone="America/Sao_Paulo"
        )
        self.assertEqual(schedules.count(), 1)

    def test_is_idempotent_for_crontab_schedule(self):
        """Rodar o comando duas vezes não duplica o CrontabSchedule."""
        call_command("setup_schedules")
        call_command("setup_schedules")

        schedules = CrontabSchedule.objects.filter(
            hour="8", minute="0", day_of_week="1", timezone="America/Sao_Paulo"
        )
        self.assertEqual(schedules.count(), 1)

    def test_creates_one_periodic_task_per_group(self):
        """Cria um PeriodicTask por CareGroup existente."""
        call_command("setup_schedules")

        self.assertEqual(
            PeriodicTask.objects.filter(task="api.tasks.send_weekly_report").count(), 2
        )

    def test_periodic_task_points_to_send_weekly_report_with_group_id_arg(self):
        """Cada PeriodicTask aponta para api.tasks.send_weekly_report com args=[group_id]."""
        call_command("setup_schedules")

        pt1 = PeriodicTask.objects.get(
            task="api.tasks.send_weekly_report", args=json.dumps([self.group1.pk])
        )
        pt2 = PeriodicTask.objects.get(
            task="api.tasks.send_weekly_report", args=json.dumps([self.group2.pk])
        )
        self.assertEqual(json.loads(pt1.args), [self.group1.pk])
        self.assertEqual(json.loads(pt2.args), [self.group2.pk])
        self.assertTrue(pt1.enabled)
        self.assertTrue(pt2.enabled)

    def test_periodic_tasks_use_the_crontab_schedule(self):
        """Os PeriodicTasks usam o CrontabSchedule criado (segunda 08h)."""
        call_command("setup_schedules")

        schedule = CrontabSchedule.objects.get(
            hour="8", minute="0", day_of_week="1", timezone="America/Sao_Paulo"
        )
        for pt in PeriodicTask.objects.filter(task="api.tasks.send_weekly_report"):
            self.assertEqual(pt.crontab_id, schedule.pk)

    def test_is_idempotent_for_periodic_tasks(self):
        """Rodar o comando duas vezes não duplica PeriodicTasks nem cria conflito."""
        call_command("setup_schedules")
        call_command("setup_schedules")

        self.assertEqual(
            PeriodicTask.objects.filter(task="api.tasks.send_weekly_report").count(), 2
        )

    def test_new_group_added_later_gets_a_periodic_task_on_rerun(self):
        """Um grupo criado após a primeira execução ganha seu PeriodicTask no rerun."""
        call_command("setup_schedules")

        patient3 = Patient.objects.create(name="Bisavó")
        group3 = CareGroup.objects.create(name="Família 3", patient=patient3)

        call_command("setup_schedules")

        self.assertTrue(
            PeriodicTask.objects.filter(
                task="api.tasks.send_weekly_report", args=json.dumps([group3.pk])
            ).exists()
        )
        self.assertEqual(
            PeriodicTask.objects.filter(task="api.tasks.send_weekly_report").count(), 3
        )
