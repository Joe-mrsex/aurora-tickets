from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('bitacora', '0001_initial')]
    operations = [migrations.AlterField(model_name='actividad', name='tipo', field=models.CharField(choices=[('CORRECTIVO', 'Mantenimiento correctivo'), ('PREVENTIVO', 'Mantenimiento preventivo'), ('INSTALACION', 'Instalación / configuración'), ('REDES', 'Redes y conectividad'), ('RESPALDO', 'Respaldos (backup)'), ('SEGURIDAD', 'Seguridad informática'), ('CUENTAS', 'Usuarios y cuentas (accesos, correo)'), ('ASESORIA', 'Asesoría / capacitación'), ('COMPRAS', 'Compras / proveedores'), ('DOCUMENTACION', 'Documentación'), ('TICKET', 'Atención de ticket'), ('OTRO', 'Otro')], default='OTRO', max_length=15))]
