from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from auditoria.servicios import Modulo, registrar
from . import temas, validators

@login_required
@require_POST
def cambiar_tema(request):
    clave = request.POST.get('tema', '')
    destino = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        destino = reverse('inicio')
    if clave in temas.TEMAS and request.user.tema != clave:
        request.user.tema = clave
        request.user.save(update_fields=['tema'])
        request.session['cambio_tema'] = True
    respuesta = redirect(destino)
    respuesta.set_cookie('tema', temas.tema_valido(request.user.tema), max_age=60 * 60 * 24 * 365, samesite='Lax', httponly=True, secure=request.is_secure())
    return respuesta

class CambioDeClaveForm(PasswordChangeForm):

    def clean(self):
        datos = super().clean()
        nueva = datos.get('new_password1')
        if nueva and self.user.check_password(nueva):
            self.add_error('new_password1', ValidationError('La contraseña nueva debe ser distinta de la actual.'))
        return datos

@login_required
def cambiar_clave(request):
    obligatorio = request.user.debe_cambiar_clave
    form = CambioDeClaveForm(request.user, request.POST or None)
    for campo, etiqueta in (('old_password', 'Contraseña actual (la temporal que te entregaron)' if obligatorio else 'Contraseña actual'), ('new_password1', 'Contraseña nueva'), ('new_password2', 'Repite la contraseña nueva')):
        form.fields[campo].label = etiqueta
    form.fields['new_password1'].help_text = validators.AYUDA
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        if usuario.debe_cambiar_clave:
            usuario.debe_cambiar_clave = False
            usuario.save(update_fields=['debe_cambiar_clave'])
        update_session_auth_hash(request, usuario)
        registrar(Modulo.USUARIOS, 'CAMBIO_CLAVE', usuario=usuario, referencia=usuario.username, detalle='La persona cambió su contraseña' + (' (primer ingreso)' if obligatorio else ''))
        messages.success(request, 'Tu contraseña se cambió correctamente.')
        destino = request.POST.get('next') or request.GET.get('next') or ''
        if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            destino = reverse('inicio')
        return redirect(destino)
    return render(request, 'accounts/cambiar_clave.html', {'form': form, 'obligatorio': obligatorio, 'next': request.GET.get('next', request.POST.get('next', ''))})
