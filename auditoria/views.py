from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from accounts.permisos import solo_jefe

from . import servicios
from .models import RegistroAuditoria

# TODA la auditoría es exclusiva del jefe de TI (@solo_jefe en cada vista).


def _filtrar(request):
    """Aplica los filtros de la URL (?q=&modulo=&desde=&hasta=) al listado."""
    registros = RegistroAuditoria.objects.all()
    q = request.GET.get("q", "").strip()
    modulo = request.GET.get("modulo", "")
    desde = parse_date(request.GET.get("desde", "") or "")
    hasta = parse_date(request.GET.get("hasta", "") or "")
    if q:
        registros = registros.filter(
            Q(usuario_nombre__icontains=q) | Q(referencia__icontains=q) | Q(detalle__icontains=q) | Q(accion__icontains=q)
        )
    if modulo:
        registros = registros.filter(modulo=modulo)
    if desde:
        registros = registros.filter(fecha__date__gte=desde)
    if hasta:
        registros = registros.filter(fecha__date__lte=hasta)
    return registros, {"q": q, "modulo": modulo, "desde": desde, "hasta": hasta}


@solo_jefe
def lista(request):
    registros, filtros = _filtrar(request)
    pagina = Paginator(registros, 50).get_page(request.GET.get("page"))
    consulta = request.GET.copy()
    consulta.pop("page", None)
    return render(request, "auditoria/lista.html", {
        "pagina": pagina, "filtros": filtros, "modulos": RegistroAuditoria.Modulo.choices,
        "consulta": consulta.urlencode(),
    })


@solo_jefe
def verificar(request):
    """Recorre la cadena de hashes y avisa si algún registro fue alterado."""
    total, problemas = servicios.verificar_cadena()
    return render(request, "auditoria/verificar.html", {"total": total, "problemas": problemas})


@solo_jefe
def depurar(request):
    """
    Depuración: el jefe elige una fecha y se borran los registros ANTERIORES a ella.
    Paso 1 (GET/POST sin confirmar): muestra cuántos registros se borrarían.
    Paso 2 (POST con confirmar=1): borra y deja constancia en la auditoría.
    """
    limite = servicios.fecha_limite_depuracion().date()
    contexto = {"limite": limite, "retencion": settings.AUDITORIA_RETENCION_MINIMA_DIAS}
    hasta = parse_date(request.POST.get("hasta") or request.GET.get("hasta") or "")

    if hasta:
        contexto["hasta"] = hasta
        if hasta > limite:
            messages.error(request, f"Solo se pueden depurar registros hasta el {limite:%d/%m/%Y} "
                                    f"(se conservan siempre los últimos {contexto['retencion']} días).")
            contexto["hasta"] = None
        else:
            contexto["cantidad"] = servicios.registros_a_depurar(hasta).count()

    if request.method == "POST" and request.POST.get("confirmar") and contexto.get("hasta"):
        try:
            borrados = servicios.depurar(contexto["hasta"], request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, f"Depuración completada: {borrados} registros eliminados.")
            return redirect("auditoria:lista")
    return render(request, "auditoria/depurar.html", contexto)
