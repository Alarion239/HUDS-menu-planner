# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_admin',
            field=models.BooleanField(default=False, help_text='Admin users can trigger manual menu fetches and other admin commands'),
        ),
    ]
