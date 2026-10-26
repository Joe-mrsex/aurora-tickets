import accounts.cifrado
from django.db import migrations


def cifrar_existentes(apps, schema_editor):
    Usuario = apps.get_model("accounts", "Usuario")
    for usuario in Usuario.objects.exclude(totp_secreto=""):
        usuario.save(update_fields=["totp_secreto"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_segundo_factor"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="totp_secreto",
            field=accounts.cifrado.CampoCifrado(blank=True, editable=False, max_length=255),
        ),
        migrations.RunPython(cifrar_existentes, migrations.RunPython.noop),
    ]
