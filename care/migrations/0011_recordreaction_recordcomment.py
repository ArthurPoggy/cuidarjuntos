from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("care", "0010_caregroup_join_code_and_carerecord_flags"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecordReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reaction", models.CharField(choices=[("heart", "Carinho"), ("clap", "Aplauso"), ("pray", "Força")], max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("record", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="reactions", to="care.carerecord")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="record_reactions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("record", "user")},
            },
        ),
        migrations.CreateModel(
            name="RecordComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(verbose_name="Comentário")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("record", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="comments", to="care.carerecord")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="record_comments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]
