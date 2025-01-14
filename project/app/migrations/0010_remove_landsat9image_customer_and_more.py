# Generated by Django 5.0.4 on 2024-06-17 06:59

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0009_remove_ndviimage_customer_remove_ndviimage_polygon_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='landsat9image',
            name='customer',
        ),
        migrations.RemoveField(
            model_name='landsat9image',
            name='polygon',
        ),
        migrations.CreateModel(
            name='LANDSATImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ndvi_image', models.ImageField(upload_to='landsat/ndvi_images/')),
                ('ndwi_image', models.ImageField(upload_to='landsat/ndwi_images/')),
                ('ndmi_image', models.ImageField(upload_to='landsat/ndmi_images/')),
                ('evi_image', models.ImageField(upload_to='landsat/evi_images/')),
                ('date', models.DateField()),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='landsat_images', to='app.customer')),
                ('polygon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='landsat_images', to='app.polygonmodel')),
            ],
        ),
        migrations.DeleteModel(
            name='LANDSAT8Image',
        ),
        migrations.DeleteModel(
            name='LANDSAT9Image',
        ),
    ]
