# Generated by Django 5.0.4 on 2024-05-31 08:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_alter_ndviimage_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='SMIValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('value', models.FloatField(null=True)),
                ('customer', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, related_name='smi_values', to='app.customer')),
                ('polygon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='smi_values', to='app.polygonmodel')),
            ],
        ),
    ]
