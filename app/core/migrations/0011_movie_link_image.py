# Generated by Django 4.0.10 on 2024-11-09 07:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_alter_genre_genre_id_alter_user_sex'),
    ]

    operations = [
        migrations.AddField(
            model_name='movie',
            name='link_image',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
