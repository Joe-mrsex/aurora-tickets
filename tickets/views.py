from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from accounts.permisos import solo_jefe, solo_ti
from . import services
from .forms import AsignarForm, ComentarioForm, EquipoForm, EstadoForm, MotivoForm, PrioridadForm, ReprogramarForm, ResolverForm, TicketForm
from .models import ESTADOS_ABIERTOS, Adjunto, Categoria, Equipo, Estado, Prioridad, Ticket
Usuario = get_user_model()

def entero_seguro(valor):
    valor = (valor or '').strip()
    return int(valor) if valor.isascii() and valor.isdigit() and (len(valor) <= 9) else None

def _tickets_visibles(usuario):
    base = Ticket.objects.select_related('solicitante', 'tecnico', 'categoria', 'equipo')
    return base if usuario.es_tecnico else base.filter(solicitante=usuario)

@login_required
def lista(request):
    tickets = _tickets_visibles(request.user)
    g = request.GET
    vista = g.get('vista', '')
    q = g.get('q', '').strip()
    if vista == 'mios':
        tickets = tickets.filter(Q(tecnico=request.user) | Q(solicitante=request.user))
    elif vista == 'sin_asignar':
        tickets = tickets.filter(tecnico__isnull=True, estado__in=ESTADOS_ABIERTOS)
    elif vista == 'abiertos':
        tickets = tickets.filter(estado__in=ESTADOS_ABIERTOS)
    elif vista == 'reprogramados':
        tickets = tickets.filter(estado__in=ESTADOS_ABIERTOS, pausado_desde__isnull=False)
    elif vista == 'vencidos':
        abiertos_vencidos = Q(estado__in=ESTADOS_ABIERTOS, pausado_desde__isnull=True, fecha_limite__lt=timezone.now())
        if g.get('abiertos') == '1':
            tickets = tickets.filter(abiertos_vencidos)
        else:
            tickets = tickets.filter(abiertos_vencidos | Q(fecha_resolucion__isnull=False, fecha_resolucion__gt=F('fecha_limite')))
    if q:
        filtro = Q(titulo__icontains=q) | Q(descripcion__icontains=q) | Q(solicitante__first_name__icontains=q) | Q(solicitante__last_name__icontains=q) | Q(solicitante__username__icontains=q)
        if q.upper().startswith('TI-') and entero_seguro(q[3:]) is not None:
            filtro |= Q(pk=entero_seguro(q[3:]))
        elif entero_seguro(q) is not None:
            filtro |= Q(pk=entero_seguro(q))
        tickets = tickets.filter(filtro)
    for campo in ('categoria', 'tecnico'):
        if entero_seguro(g.get(campo)) is not None:
            tickets = tickets.filter(**{f'{campo}_id': entero_seguro(g.get(campo))})
    if g.get('estado') in Estado.values:
        tickets = tickets.filter(estado=g['estado'])
    if g.get('prioridad') in Prioridad.values:
        tickets = tickets.filter(prioridad=g['prioridad'])
    pagina = Paginator(tickets, 25).get_page(g.get('page'))
    consulta = g.copy()
    consulta.pop('page', None)
    return render(request, 'tickets/lista.html', {'pagina': pagina, 'vista': vista, 'q': q, 'consulta': consulta.urlencode(), 'estados': Estado.choices, 'prioridades': Prioridad.choices, 'categorias': Categoria.objects.all(), 'tecnicos': Usuario.personal_ti(), 'filtro': {k: g.get(k, '') for k in ('estado', 'prioridad', 'categoria', 'tecnico')}})

@login_required
def crear(request):
    form = TicketForm(request.POST or None, request.FILES or None, usuario=request.user)
    if request.method == 'POST' and form.is_valid():
        datos = form.cleaned_data
        ticket = services.crear_ticket(solicitante=request.user, titulo=datos['titulo'], descripcion=datos['descripcion'], categoria=datos['categoria'], prioridad=datos['prioridad'], equipo=datos['equipo'], archivos=datos['archivos'])
        messages.success(request, f'Tu ticket {ticket.codigo} fue registrado. Te atenderemos lo antes posible.')
        return redirect('tickets:detalle', pk=ticket.pk)
    return render(request, 'tickets/crear.html', {'form': form})

@login_required
def detalle(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related('solicitante', 'tecnico', 'categoria', 'equipo'), pk=pk)
    if not services.puede_ver(request.user, ticket):
        raise PermissionDenied
    usuario = request.user
    if request.method == 'POST':
        accion = request.POST.get('accion', '')
        try:
            _ejecutar_accion(request, ticket, accion)
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
        except PermissionDenied as error:
            messages.error(request, str(error) or 'No tienes permiso para esta acción.')
        return redirect('tickets:detalle', pk=ticket.pk)
    comentarios = ticket.comentarios.select_related('autor')
    historial = ticket.historial.select_related('usuario')
    adjuntos = ticket.adjuntos.select_related('subido_por')
    if not usuario.es_tecnico:
        comentarios = comentarios.filter(interno=False)
        historial = historial.filter(visible_solicitante=True)
        adjuntos = adjuntos.exclude(comentario__interno=True)
    contexto = {'ticket': ticket, 'comentarios': comentarios, 'historial': historial, 'adjuntos': adjuntos, 'actividades': ticket.actividades.select_related('tecnico'), 'form_comentario': ComentarioForm(es_ti=usuario.es_tecnico), 'es_solicitante': ticket.solicitante_id == usuario.id}
    if usuario.es_tecnico:
        opciones = [e for e in services.TRANSICIONES_TI.get(ticket.estado, []) if e not in (Estado.RESUELTO, Estado.CERRADO, Estado.ASIGNADO)]
        if ticket.estado == Estado.CERRADO and (not usuario.es_jefe):
            opciones = []
        contexto.update({'form_asignar': AsignarForm(initial={'tecnico': ticket.tecnico_id or usuario.pk}), 'form_estado': EstadoForm(opciones=opciones), 'opciones_estado': opciones, 'form_resolver': ResolverForm(), 'form_prioridad': PrioridadForm(initial={'prioridad': ticket.prioridad}), 'form_reprogramar': ReprogramarForm(), 'puede_resolver': Estado.RESUELTO in services.TRANSICIONES_TI.get(ticket.estado, []), 'puede_tomar': ticket.estado == Estado.NUEVO or (ticket.estado == Estado.ASIGNADO and ticket.tecnico_id in (None, usuario.id))})
    if contexto['es_solicitante'] and ticket.estado == Estado.RESUELTO:
        contexto['form_motivo'] = MotivoForm()
    return render(request, 'tickets/detalle.html', contexto)

def _ejecutar_accion(request, ticket, accion):
    usuario, post = (request.user, request.POST)
    if accion == 'comentar':
        form = ComentarioForm(post, request.FILES, es_ti=usuario.es_tecnico)
        if not form.is_valid():
            raise ValidationError(' '.join((e for errs in form.errors.values() for e in errs)))
        comentario = services.comentar(ticket, usuario, form.cleaned_data['texto'], form.cleaned_data.get('interno', False))
        for archivo in form.cleaned_data['archivos']:
            services.adjuntar(ticket, usuario, archivo, comentario)
        messages.success(request, 'Comentario agregado.')
    elif accion == 'tomar':
        services.tomar(ticket, usuario)
        messages.success(request, 'Ahora eres el responsable de este ticket.')
    elif accion == 'asignar':
        form = AsignarForm(post)
        if not form.is_valid():
            raise ValidationError('Selecciona un técnico válido.')
        services.asignar(ticket, form.cleaned_data['tecnico'], usuario)
        messages.success(request, 'Ticket asignado.')
    elif accion == 'estado':
        opciones = [e for e in services.TRANSICIONES_TI.get(ticket.estado, []) if e != Estado.ASIGNADO]
        form = EstadoForm(post, opciones=opciones)
        if not form.is_valid():
            raise ValidationError('Estado no válido para este ticket.')
        services.cambiar_estado(ticket, form.cleaned_data['estado'], usuario, form.cleaned_data['nota'])
        messages.success(request, 'Estado actualizado.')
    elif accion == 'resolver':
        form = ResolverForm(post)
        if not form.is_valid():
            raise ValidationError('Describe la solución aplicada.')
        services.resolver(ticket, form.cleaned_data['solucion'], usuario, form.cleaned_data['minutos'] or 0)
        messages.success(request, 'Ticket resuelto. Quedó registrado en la bitácora automáticamente.')
    elif accion == 'cerrar':
        services.cerrar(ticket, usuario)
        messages.success(request, 'Ticket cerrado. ¡Gracias por confirmar!')
    elif accion == 'reabrir':
        form = MotivoForm(post)
        if not form.is_valid():
            raise ValidationError('Indica el motivo.')
        if usuario.es_tecnico:
            services.cambiar_estado(ticket, Estado.EN_PROCESO, usuario, form.cleaned_data['motivo'])
        else:
            services.reabrir_por_solicitante(ticket, usuario, form.cleaned_data['motivo'])
        messages.success(request, 'Ticket reabierto.')
    elif accion == 'reprogramar':
        form = ReprogramarForm(post)
        if not form.is_valid():
            raise ValidationError(' '.join((e for errs in form.errors.values() for e in errs)))
        services.reprogramar(ticket, form.cleaned_data['fecha'], form.cleaned_data['motivo'], usuario)
        messages.success(request, f"Ticket reprogramado para el {form.cleaned_data['fecha']:%d/%m/%Y}. El SLA quedó en pausa y se avisó al solicitante.")
    elif accion == 'retomar':
        services.retomar(ticket, usuario)
        messages.success(request, 'Ticket retomado: el SLA volvió a correr.')
    elif accion == 'prioridad':
        form = PrioridadForm(post)
        if not form.is_valid():
            raise ValidationError('Prioridad no válida.')
        services.cambiar_prioridad(ticket, form.cleaned_data['prioridad'], usuario)
        messages.success(request, 'Prioridad actualizada.')
    else:
        raise ValidationError('Acción desconocida.')

@login_required
def descargar_adjunto(request, pk):
    adjunto = get_object_or_404(Adjunto.objects.select_related('ticket', 'comentario'), pk=pk)
    if not services.puede_ver_adjunto(request.user, adjunto):
        raise PermissionDenied
    try:
        archivo = adjunto.archivo.open('rb')
    except FileNotFoundError:
        raise Http404('El archivo ya no existe en el servidor.') from None
    respuesta = FileResponse(archivo, as_attachment=True, filename=adjunto.nombre_original, content_type='application/octet-stream')
    respuesta['X-Content-Type-Options'] = 'nosniff'
    respuesta['Cache-Control'] = 'private, no-store'
    return respuesta

@solo_ti
def equipos_lista(request):
    q = request.GET.get('q', '').strip()
    equipos = Equipo.objects.select_related('asignado_a')
    if q:
        equipos = equipos.filter(Q(codigo__icontains=q) | Q(serial__icontains=q) | Q(marca__icontains=q) | Q(modelo__icontains=q) | Q(asignado_a__first_name__icontains=q) | Q(asignado_a__last_name__icontains=q) | Q(asignado_a__username__icontains=q) | Q(ubicacion__icontains=q))
    pagina = Paginator(equipos, 30).get_page(request.GET.get('page'))
    return render(request, 'tickets/equipos_lista.html', {'pagina': pagina, 'q': q})

@solo_ti
def equipo_form(request, pk=None):
    equipo = get_object_or_404(Equipo, pk=pk) if pk else None
    form = EquipoForm(request.POST or None, instance=equipo)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Equipo guardado.')
        return redirect('tickets:equipos')
    historial = equipo.tickets.select_related('solicitante')[:20] if equipo else []
    return render(request, 'tickets/equipo_form.html', {'form': form, 'equipo': equipo, 'historial': historial})

@solo_jefe
def equipo_eliminar(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    if request.method == 'POST':
        equipo.delete()
        messages.success(request, 'Equipo eliminado.')
        return redirect('tickets:equipos')
    return render(request, 'confirmar_eliminar.html', {'objeto': equipo, 'volver': 'tickets:equipos'})
