from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('screening', '0010_offerletter_candidatedocument'),
    ]

    operations = [
        migrations.AddField(
            model_name='offerletter',
            name='letter_file',
            field=models.FileField(blank=True, null=True, upload_to='offer_letters/'),
        ),
    ]
