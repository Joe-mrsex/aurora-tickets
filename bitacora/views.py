from datetime import timedelta
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from accounts.permisos import solo_jefe, solo_ti
from tickets.models import ESTADOS_ABIERTOS, Equipo, Ticket
from tickets.views import entero_seguro
from . import matriz
from .models import Actividad
Usuario = get_user_model()
DIAS_TICKETS_EN_FORMULARIO = 60

class ActividadForm(forms.ModelForm):

    class Meta:
        model = Actividad
        fields = ['fecha', 'tipo', 'titulo', 'descripcion', 'duracion_minutos', 'equipo', 'ticket']
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'), 'descripcion': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['equipo'].queryset = Equipo.objects.filter(activo=True)
        ofrecidos = Q(estado__in=ESTADOS_ABIERTOS) | Q(actualizado__gte=timezone.now() - timedelta(days=DIAS_TICKETS_EN_FORMULARIO))
        if self.instance.ticket_id:
            ofrecidos |= Q(pk=self.instance.ticket_id)
        self.fields['ticket'].queryset = Ticket.objects.filter(ofrecidos).order_by('-id')
        self.fields['equipo'].required = False
        self.fields['ticket'].required = False

@solo_ti
def lista(request):
    g = request.GET
    actividades = Actividad.objects.select_related('tecnico', 'equipo', 'ticket')
    q = g.get('q', '').strip()
    desde, hasta = (parse_date(g.get('desde', '') or ''), parse_date(g.get('hasta', '') or ''))
    tecnico = g.get('tecnico', '')
    if not request.user.es_jefe:
        actividades = actividades.filter(tecnico=request.user)
    elif entero_seguro(tecnico) is not None:
        actividades = actividades.filter(tecnico_id=entero_seguro(tecnico))
    if q:
        actividades = actividades.filter(Q(titulo__icontains=q) | Q(descripcion__icontains=q))
    if g.get('tipo'):
        actividades = actividades.filter(tipo=g['tipo'])
    if desde:
        actividades = actividades.filter(fecha__gte=desde)
    if hasta:
        actividades = actividades.filter(fecha__lte=hasta)
    total_min = actividades.aggregate(t=Sum('duracion_minutos'))['t'] or 0
    pagina = Paginator(actividades, 30).get_page(g.get('page'))
    consulta = g.copy()
    consulta.pop('page', None)
    return render(request, 'bitacora/lista.html', {'pagina': pagina, 'q': q, 'tipos': Actividad.Tipo.choices, 'consulta': consulta.urlencode(), 'tecnicos': Usuario.personal_ti(solo_activos=False), 'total_horas': round(total_min / 60, 1), 'filtro': {'tipo': g.get('tipo', ''), 'tecnico': tecnico, 'desde': g.get('desde', ''), 'hasta': g.get('hasta', '')}})

@solo_ti
def crear(request):
    form = ActividadForm(request.POST or None, initial={'fecha': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        actividad = form.save(commit=False)
        actividad.tecnico = request.user
        actividad.save()
        messages.success(request, 'Actividad registrada en la bitácora.')
        return redirect('bitacora:lista')
    return render(request, 'bitacora/form.html', {'form': form, 'titulo': 'Registrar actividad'})

@solo_ti
def editar(request, pk):
    actividad = get_object_or_404(Actividad, pk=pk)
    if actividad.automatica or (actividad.tecnico_id != request.user.id and (not request.user.es_jefe)):
        raise PermissionDenied
    form = ActividadForm(request.POST or None, instance=actividad)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Actividad actualizada (el cambio quedó auditado).')
        return redirect('bitacora:lista')
    return render(request, 'bitacora/form.html', {'form': form, 'titulo': f'Editar actividad #{actividad.pk}'})

@solo_jefe
def eliminar(request, pk):
    actividad = get_object_or_404(Actividad, pk=pk)
    if request.method == 'POST':
        actividad.delete()
        messages.success(request, 'Actividad eliminada (quedó registrado en la auditoría).')
        return redirect('bitacora:lista')
    return render(request, 'confirmar_eliminar.html', {'objeto': actividad, 'volver': 'bitacora:lista'})

@solo_ti
def descargar_matriz(request):
    desde = parse_date(request.GET.get('desde', '') or '')
    hasta = parse_date(request.GET.get('hasta', '') or '')
    if request.user.es_jefe:
        tecnico_id = request.GET.get('tecnico', '')
        if tecnico_id and entero_seguro(tecnico_id) is None:
            raise Http404('Técnico no válido.')
        tecnico = get_object_or_404(Usuario.personal_ti(solo_activos=False), pk=entero_seguro(tecnico_id)) if tecnico_id else None
    else:
        tecnico = request.user
    libro = matriz.construir_matriz(tecnico, desde, hasta)
    nombre = tecnico.username if tecnico else 'todos'
    respuesta = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    respuesta['Content-Disposition'] = f'attachment; filename="Matriz_Actividades_{nombre}_{timezone.localdate():%Y%m%d}.xlsx"'
    libro.save(respuesta)
    return respuesta
