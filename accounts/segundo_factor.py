"""
Segundo factor de autenticación: la lógica (los códigos de recuperación, el «recordar este equipo» y los bloqueos) y las pantallas.

Resumen del recorrido de una persona (con TICKETS_2FA=True):
  1. Entra con usuario y contraseña (y, si es temporal, elige una propia).
  2. Primera vez: escanea un QR con su celular y confirma con un código; el sistema le da códigos de recuperación para guardar.
  3. Siguientes veces: escribe el código de 6 dígitos del celular (o lo omite en un equipo que marcó como «recordar 30 días»).
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.signing import BadSignature
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe

from auditoria.servicios import Modulo, registrar

from . import totp
from .models import CodigoRecuperacion

SESION_OK = "segundo_factor_ok"
SESION_PENDIENTE = "segundo_factor_secreto_pendiente"
COOKIE = "dispositivo_2fa"
SAL = "accounts.dispositivo_2fa"
EMISOR = f"{settings.NOMBRE_SISTEMA} ({settings.SUBTITULO_SISTEMA})"
CODIGOS_DE_RECUPERACION = 8
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin I, O, 0 ni 1


def _huella(codigo_texto):
    return hashlib.sha256((settings.SECRET_KEY + "|recuperacion|" + codigo_texto).encode("utf-8")).hexdigest()


def _normalizar(texto):
    return "".join(c for c in (texto or "").upper() if c.isalnum())


def crear_codigos(usuario):
    """Genera códigos de recuperación nuevos (invalidando los anteriores) y los devuelve en claro UNA sola vez; en la base solo queda su huella."""
    CodigoRecuperacion.objects.filter(usuario=usuario).delete()
    entregados = []
    for _ in range(CODIGOS_DE_RECUPERACION):
        crudo = "".join(secrets.choice(ALFABETO) for _ in range(10))
        CodigoRecuperacion.objects.create(usuario=usuario, huella=_huella(crudo))
        entregados.append(f"{crudo[:5]}-{crudo[5:]}")
    return entregados


def usar_codigo_de_recuperacion(usuario, texto):
    """True si el texto es un código de recuperación sin usar; lo deja gastado."""
    normal = _normalizar(texto)
    if len(normal) != 10:
        return False
    huella = _huella(normal)
    for fila in CodigoRecuperacion.objects.filter(usuario=usuario, usado=False):
        if hmac.compare_digest(fila.huella, huella):
            fila.usado = True
            fila.save(update_fields=["usado"])
            return True
    return False


def reiniciar(usuario):
    """Quita el segundo factor (la persona perdió el celular): tendrá que activarlo de nuevo. También invalida todos sus «equipos recordados»."""
    CodigoRecuperacion.objects.filter(usuario=usuario).delete()
    usuario.totp_secreto = ""
    usuario.totp_activo = False
    usuario.totp_ultimo_paso = 0
    usuario.totp_fallos = 0
    usuario.totp_bloqueado_hasta = None
    usuario.totp_epoca += 1
    usuario.save(update_fields=["totp_secreto", "totp_activo", "totp_ultimo_paso", "totp_fallos", "totp_bloqueado_hasta", "totp_epoca"])


def verificado(request):
    return request.session.get(SESION_OK) == request.user.pk


def marcar_verificado(request):
    request.session[SESION_OK] = request.user.pk


def equipo_recordado(request, usuario):
    """Cookie firmada con el id del usuario y su «época»: si se reinicia su segundo factor, las cookies viejas dejan de valer."""
    try:
        valor = request.get_signed_cookie(COOKIE, salt=SAL, max_age=settings.DIAS_EQUIPO_RECORDADO * 86400)
    except (KeyError, BadSignature):
        return False
    return usuario.totp_activo and valor == f"{usuario.pk}:{usuario.totp_epoca}"


def recordar_equipo(respuesta, request, usuario):
    respuesta.set_signed_cookie(COOKIE, f"{usuario.pk}:{usuario.totp_epoca}", salt=SAL, max_age=settings.DIAS_EQUIPO_RECORDADO * 86400,
                                httponly=True, samesite="Lax", secure=request.is_secure())


def _destino(request):
    destino = request.POST.get("next") or request.GET.get("next") or ""
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return destino
    return reverse("inicio")


def _bloqueado(usuario):
    return bool(usuario.totp_bloqueado_hasta and usuario.totp_bloqueado_hasta > timezone.now())


def _anotar_fallo(usuario, request):
    usuario.totp_fallos += 1
    bloquear = usuario.totp_fallos >= settings.TOTP_INTENTOS
    if bloquear:
        usuario.totp_bloqueado_hasta = timezone.now() + timedelta(minutes=settings.TOTP_BLOQUEO_MINUTOS)
        usuario.totp_fallos = 0
    usuario.save(update_fields=["totp_fallos", "totp_bloqueado_hasta"])
    registrar(Modulo.ACCESO, "SEGUNDO_FACTOR_FALLIDO", usuario=usuario, referencia=usuario.username,
              detalle="Código del segundo factor incorrecto" + (f"; bloqueado {settings.TOTP_BLOQUEO_MINUTOS} minutos" if bloquear else ""))


@login_required
def verificar(request):
    usuario = request.user
    destino = _destino(request)
    if not settings.SEGUNDO_FACTOR or verificado(request):
        return redirect(destino)
    if not usuario.totp_activo:
        return redirect(reverse("accounts:activar_2fa") + ("?next=" + destino if destino != reverse("inicio") else ""))
    error = ""
    if request.method == "POST":
        if _bloqueado(usuario):
            error = "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."
        else:
            texto = request.POST.get("codigo", "")
            paso = totp.verificar(usuario.totp_secreto, texto, ultimo_paso=usuario.totp_ultimo_paso)
            if paso is not None:
                usuario.totp_ultimo_paso = paso
                usuario.totp_fallos = 0
                usuario.save(update_fields=["totp_ultimo_paso", "totp_fallos"])
            elif usar_codigo_de_recuperacion(usuario, texto):
                usuario.totp_fallos = 0
                usuario.save(update_fields=["totp_fallos"])
                quedan = CodigoRecuperacion.objects.filter(usuario=usuario, usado=False).count()
                messages.warning(request, f"Entraste con un código de recuperación. Te quedan {quedan}. Si perdiste el celular, avisa a TI para activar el segundo factor otra vez.")
                registrar(Modulo.ACCESO, "CODIGO_DE_RECUPERACION", usuario=usuario, referencia=usuario.username, detalle="Entró con un código de recuperación")
            else:
                _anotar_fallo(usuario, request)
                error = "El código no es correcto."
            if not error:
                marcar_verificado(request)
                respuesta = redirect(destino)
                if request.POST.get("recordar"):
                    recordar_equipo(respuesta, request, usuario)
                return respuesta
    return render(request, "accounts/verificar_2fa.html", {"error": error, "next": destino, "dias": settings.DIAS_EQUIPO_RECORDADO})


@login_required
def activar(request):
    usuario = request.user
    if not settings.SEGUNDO_FACTOR or usuario.totp_activo:
        return redirect(reverse("inicio"))
    secreto = request.session.get(SESION_PENDIENTE)
    if not secreto:
        secreto = request.session[SESION_PENDIENTE] = totp.generar_secreto()
    error = ""
    if request.method == "POST":
        paso = totp.verificar(secreto, request.POST.get("codigo", ""))
        if paso is None:
            error = "El código no es correcto. Comprueba que escaneaste el QR y que la hora del celular es la correcta."
        else:
            usuario.totp_secreto = secreto
            usuario.totp_activo = True
            usuario.totp_ultimo_paso = paso
            usuario.totp_fallos = 0
            usuario.save(update_fields=["totp_secreto", "totp_activo", "totp_ultimo_paso", "totp_fallos"])
            request.session.pop(SESION_PENDIENTE, None)
            marcar_verificado(request)
            registrar(Modulo.USUARIOS, "ACTIVAR_SEGUNDO_FACTOR", usuario=usuario, referencia=usuario.username, detalle="La persona activó el segundo factor")
            respuesta = render(request, "accounts/codigos_recuperacion.html", {"codigos": crear_codigos(usuario), "next": _destino(request)})
            if request.POST.get("recordar"):
                recordar_equipo(respuesta, request, usuario)
            return respuesta
    uri = totp.uri_aprovisionamiento(secreto, usuario.username, EMISOR)
    return render(request, "accounts/activar_2fa.html", {
        "qr": mark_safe(totp.qr_svg(uri)), "secreto": " ".join(secreto[i:i + 4] for i in range(0, len(secreto), 4)),
        "error": error, "next": _destino(request), "dias": settings.DIAS_EQUIPO_RECORDADO})
