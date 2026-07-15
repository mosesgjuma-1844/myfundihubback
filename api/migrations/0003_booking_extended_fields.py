from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_booking'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='assigned_technician',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='assigned_bookings', to='auth.user'),
        ),
        migrations.AddField(
            model_name='booking',
            name='county',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='booking',
            name='town_or_estate',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='booking',
            name='landmark',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='booking',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
    ]
