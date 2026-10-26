from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [migrations.AddField(model_name='usuario', name='tema', field=models.CharField(choices=[('titanio', 'Titanio'), ('grafito', 'Grafito'), ('neon', 'Neón'), ('tinta', 'Tinta')], default='titanio', max_length=12, verbose_name='Tema visual'))]
