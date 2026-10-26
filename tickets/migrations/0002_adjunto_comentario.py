import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('tickets', '0001_initial')]
    operations = [migrations.AddField(model_name='adjunto', name='comentario', field=models.ForeignKey(blank=True, help_text='Si el comentario es una nota interna, el archivo solo lo ve TI.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='adjuntos', to='tickets.comentario'))]
