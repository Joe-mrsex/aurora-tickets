from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.permisos import solo_ti
from bitacora.models import Actividad
from tickets.models import ESTADOS_ABIERTOS, Estado, Prioridad, Ticket

Usuario = get_user_model()


@login_required
def inicio(request):
    """Página de inicio: TI va al panel de control; el personal, a sus tickets."""
    if request.user.es_tecnico:
        return redirect("dashboard:panel")
    return redirect("tickets:lista")


def _barras(pares):
    """[(etiqueta, valor)] -> [{etiqueta, valor, porcentaje}] para dibujar barras con CSS."""
    maximo = max((v for _, v in pares), default=0) or 1
    return [{"etiqueta": e, "valor": v, "pct": round(v * 100 / maximo)} for e, v in pares]


def _promedio_horas(deltas):
    deltas = [d for d in deltas if d is not None]
    if not deltas:
        return None
    return round(sum(d.total_seconds() for d in deltas) / len(deltas) / 3600, 1)


@solo_ti
def panel(request):
    try:
        dias = int(request.GET.get("dias", 30))
    except ValueError:
        dias = 30
    dias = dias if dias in (7, 30, 90, 365) else 30
    ahora = timezone.now()
    desde = ahora - timedelta(days=dias)

    todos = Ticket.objects.all()
    abiertos = todos.filter(estado__in=ESTADOS_ABIERTOS)
    sin_pausa = abiertos.filter(pausado_desde__isnull=True)  # los reprogramados tienen el SLA en pausa: no cuentan como vencidos
    creados_periodo = todos.filter(creado__gte=desde)
    resueltos_periodo = list(todos.filter(fecha_resolucion__gte=desde).select_related("tecnico", "categoria"))

    con_sla = [t for t in resueltos_periodo if t.cumplio_sla is not None]
    cumplidos = sum(1 for t in con_sla if t.cumplio_sla)
    cumplimiento = round(cumplidos * 100 / len(con_sla)) if con_sla else None

    corriendo = Q(pausado_desde__isnull=True)  # SLA en marcha (no reprogramado)
    por_vencer_hasta = ahora + timedelta(hours=settings.SLA_AVISO_HORAS)  # el mismo margen con el que se avisa al técnico
    cuenta = abiertos.aggregate(  # una sola consulta para todas las cifras de tickets abiertos
        abiertos=Count("id"),
        sin_asignar=Count("id", filter=Q(tecnico__isnull=True)),
        vencidos=Count("id", filter=corriendo & Q(fecha_limite__lt=ahora)),
        por_vencer=Count("id", filter=corriendo & Q(fecha_limite__gte=ahora, fecha_limite__lt=por_vencer_hasta)),
        reprogramados=Count("id", filter=Q(pausado_desde__isnull=False)),
    )
    kpis = {
        **cuenta,
        "creados": creados_periodo.count(),
        "resueltos": len(resueltos_periodo),
        "cumplimiento": cumplimiento,
        "tiempo_resolucion": _promedio_horas([t.tiempo_resolucion for t in resueltos_periodo]),
        "primera_atencion": _promedio_horas([
            (t.fecha_primera_atencion - t.creado) if t.fecha_primera_atencion else None
            for t in creados_periodo.only("creado", "fecha_primera_atencion")
        ]),
    }

    # Tickets abiertos por estado y por prioridad
    en_estado = dict(abiertos.order_by().values_list("estado").annotate(n=Count("id")))
    en_prioridad = dict(abiertos.order_by().values_list("prioridad").annotate(n=Count("id")))
    por_estado = _barras([(Estado(e).label, en_estado.get(e, 0)) for e in ESTADOS_ABIERTOS])
    por_prioridad = _barras([(Prioridad(p).label, en_prioridad.get(p, 0)) for p in
                             (Prioridad.CRITICA, Prioridad.ALTA, Prioridad.MEDIA, Prioridad.BAJA)])

    # Categorías y departamentos con más tickets en el período
    por_categoria = _barras([
        (r["categoria__nombre"], r["n"]) for r in
        creados_periodo.values("categoria__nombre").annotate(n=Count("id")).order_by("-n")[:8]
    ])
    por_departamento = _barras([
        (r["solicitante__departamento"] or "(sin departamento)", r["n"]) for r in
        creados_periodo.values("solicitante__departamento").annotate(n=Count("id")).order_by("-n")[:8]
    ])
    top_equipos = list(
        creados_periodo.exclude(equipo__isnull=True).values("equipo__codigo", "equipo__marca", "equipo__modelo")
        .annotate(n=Count("id")).order_by("-n")[:5]
    )

    # Carga por técnico
    abiertos_de = dict(abiertos.filter(tecnico__isnull=False).order_by().values_list("tecnico").annotate(n=Count("id")))
    bitacora_de = {r["tecnico"]: r for r in Actividad.objects.filter(fecha__gte=desde.date()).order_by()
                   .values("tecnico").annotate(n=Count("id"), minutos=Sum("duracion_minutos"))}
    resueltos_de = defaultdict(list)
    for t in resueltos_periodo:
        resueltos_de[t.tecnico_id].append(t)
    tecnicos = []
    for tec in Usuario.personal_ti():
        resueltos_tec = resueltos_de[tec.id]
        bitacora = bitacora_de.get(tec.id, {})
        tecnicos.append({
            "nombre": tec.nombre_completo,
            "abiertos": abiertos_de.get(tec.id, 0),
            "resueltos": len(resueltos_tec),
            "tiempo_medio": _promedio_horas([t.tiempo_resolucion for t in resueltos_tec]),
            "actividades": bitacora.get("n", 0),
            "horas": round((bitacora.get("minutos") or 0) / 60, 1),
        })

    # Serie diaria: creados vs resueltos (máx. 30 barras para que se lea bien)
    tramo = min(dias, 30)
    inicio_serie = (ahora - timedelta(days=tramo - 1)).date()
    creados_dia = {r["d"]: r["n"] for r in
                   todos.filter(creado__date__gte=inicio_serie).annotate(d=TruncDate("creado")).values("d").annotate(n=Count("id"))}
    resueltos_dia = {r["d"]: r["n"] for r in
                     todos.filter(fecha_resolucion__date__gte=inicio_serie).annotate(d=TruncDate("fecha_resolucion"))
                     .values("d").annotate(n=Count("id"))}
    serie = []
    for i in range(tramo):
        dia = inicio_serie + timedelta(days=i)
        serie.append({"dia": dia, "creados": creados_dia.get(dia, 0), "resueltos": resueltos_dia.get(dia, 0)})
    maximo = max([s["creados"] for s in serie] + [s["resueltos"] for s in serie] + [1])
    for s in serie:
        s["h_creados"] = round(s["creados"] * 100 / maximo)
        s["h_resueltos"] = round(s["resueltos"] * 100 / maximo)

    return render(request, "dashboard/panel.html", {
        "dias": dias, "opciones_dias": (7, 30, 90, 365), "kpis": kpis,
        "por_estado": por_estado, "por_prioridad": por_prioridad, "por_categoria": por_categoria,
        "por_departamento": por_departamento, "top_equipos": top_equipos, "tecnicos": tecnicos, "serie": serie,
        "vencidos": sin_pausa.filter(fecha_limite__lt=ahora).select_related("solicitante", "tecnico").order_by("fecha_limite")[:8],
        "sin_asignar": abiertos.filter(tecnico__isnull=True).select_related("solicitante").order_by("fecha_limite")[:8],
        "ultimas_actividades": Actividad.objects.select_related("tecnico")[:8],
    })
