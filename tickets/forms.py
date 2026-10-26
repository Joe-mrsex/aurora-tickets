import zipfile
from datetime import timedelta
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Categoria, Equipo, Estado, Prioridad, Ticket

Usuario = get_user_model()

# Se permiten solo formatos que NO pueden llevar macros ni ejecutarse: imágenes, PDF, texto y Office moderno
# (.docx/.xlsx). Se excluyen .doc/.xls (admiten macros) y .zip (puede esconder ejecutables).
EXTENSIONES_PERMITIDAS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".txt", ".log", ".docx", ".xlsx"}

FIRMAS = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".pdf": (b"%PDF-",),
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
}
# Cabeceras de ejecutables de Linux/macOS: se rechazan SIEMPRE, sea cual sea la extensión declarada
CABECERAS_EJECUTABLES = (b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe")


def _es_ejecutable_windows(cabecera):
    """Un .exe/.dll empieza por «MZ» y en el offset 0x3C apunta a la firma «PE\0\0» (evita falsos positivos con texto «MZ-001»)."""
    if not cabecera.startswith(b"MZ") or len(cabecera) < 0x40:
        return False
    desplazamiento = int.from_bytes(cabecera[0x3C:0x40], "little")
    return desplazamiento < len(cabecera) - 3 and cabecera[desplazamiento:desplazamiento + 4] == b"PE\x00\x00" \
        or desplazamiento > len(cabecera)  # PE más allá de lo leído: sigue siendo sospechoso con «MZ» inicial


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Campo que acepta varios archivos a la vez (patrón oficial de la documentación de Django)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpiar = super().clean
        if isinstance(data, (list, tuple)):
            return [limpiar(archivo, initial) for archivo in data]
        return [limpiar(data, initial)] if data else []


# Extensiones que nunca se aceptan, ni como nombre del archivo ni dentro de un documento de Office
EXTENSIONES_PELIGROSAS = {".exe", ".dll", ".bat", ".cmd", ".com", ".scr", ".msi", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf",
                          ".hta", ".jar", ".lnk", ".reg", ".docm", ".xlsm", ".pptm", ".html", ".htm", ".svg", ".php", ".py", ".sh"}


def _nombre_seguro(nombre):
    nombre = Path(nombre).name
    sufijos = [x.lower() for x in Path(nombre).suffixes]
    # Doble extensión tipo «factura.pdf.exe» o «foto.exe.png»: ninguna parte puede ser peligrosa
    return not any(x in EXTENSIONES_PELIGROSAS for x in sufijos) and "\x00" not in nombre


def validar_archivo(archivo):
    nombre = archivo.name
    extension = Path(nombre).suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS or not _nombre_seguro(nombre):
        raise forms.ValidationError(f"«{nombre}»: tipo de archivo no permitido.")
    if archivo.size > settings.MAX_ADJUNTO_MB * 1024 * 1024:
        raise forms.ValidationError(f"«{nombre}» supera {settings.MAX_ADJUNTO_MB} MB.")
    if archivo.size == 0:
        raise forms.ValidationError(f"«{nombre}» está vacío.")
    # Se mira el CONTENIDO real: renombrar un .exe a .pdf no sirve
    archivo.seek(0)
    cabecera = archivo.read(2048)
    archivo.seek(0)
    if cabecera.startswith(CABECERAS_EJECUTABLES) or _es_ejecutable_windows(cabecera):
        raise forms.ValidationError(f"«{nombre}»: el contenido no es un documento permitido.")
    firmas = FIRMAS.get(extension)
    if firmas and not cabecera.startswith(firmas):
        raise forms.ValidationError(f"«{nombre}»: el contenido no coincide con su extensión.")
    if extension in (".txt", ".log") and b"\x00" in cabecera:
        raise forms.ValidationError(f"«{nombre}»: no es un archivo de texto.")
    if extension in (".docx", ".xlsx"):
        try:
            with zipfile.ZipFile(archivo) as z:
                nombres = [n.lower() for n in z.namelist()]
                # Un .docx/.xlsx real siempre trae este índice: sin él es un .zip cualquiera con la extensión cambiada
                if "[content_types].xml" not in nombres:
                    raise forms.ValidationError(f"«{nombre}»: no es un documento de Office válido.")
                if any(n.endswith("vbaproject.bin") or Path(n).suffix in EXTENSIONES_PELIGROSAS for n in nombres):
                    raise forms.ValidationError(f"«{nombre}»: contiene macros o ejecutables.")
                if sum(i.file_size for i in z.infolist()) > 200 * 1024 * 1024:  # bomba de descompresión
                    raise forms.ValidationError(f"«{nombre}»: archivo sospechoso.")
        except zipfile.BadZipFile:
            raise forms.ValidationError(f"«{nombre}»: el documento está dañado.") from None
        finally:
            archivo.seek(0)


class TicketForm(forms.ModelForm):
    archivos = MultipleFileField(required=False, label="Adjuntos (capturas, documentos)")

    class Meta:
        model = Ticket
        fields = ["titulo", "categoria", "prioridad", "equipo", "descripcion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Categoria.objects.filter(activa=True)
        if usuario.es_tecnico:
            equipos = Equipo.objects.filter(activo=True)
        else:
            equipos = Equipo.objects.filter(activo=True, asignado_a=usuario)
            # Un solicitante no puede marcar «Crítica»: esa la decide TI al revisar.
            self.fields["prioridad"].choices = [c for c in Prioridad.choices if c[0] != Prioridad.CRITICA]
        self.fields["equipo"].queryset = equipos
        self.fields["equipo"].required = False
        self.fields["equipo"].empty_label = "— No aplica / no sé —"

    def clean_archivos(self):
        archivos = self.cleaned_data.get("archivos") or []
        for archivo in archivos:
            validar_archivo(archivo)
        return archivos


class ComentarioForm(forms.Form):
    texto = forms.CharField(label="Comentario", widget=forms.Textarea(attrs={"rows": 3}))
    interno = forms.BooleanField(required=False, label="Nota interna (solo la ve TI)")
    archivos = MultipleFileField(required=False, label="Adjuntar archivos")

    def __init__(self, *args, es_ti=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not es_ti:
            del self.fields["interno"]  # el solicitante ni siquiera ve la casilla (el servidor igual la ignoraría)

    def clean_archivos(self):
        archivos = self.cleaned_data.get("archivos") or []
        for archivo in archivos:
            validar_archivo(archivo)
        return archivos


class AsignarForm(forms.Form):
    tecnico = forms.ModelChoiceField(queryset=Usuario.objects.none(), label="Asignar a")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tecnico"].queryset = Usuario.personal_ti()


class EstadoForm(forms.Form):
    estado = forms.ChoiceField(label="Nuevo estado")
    nota = forms.CharField(label="Nota (opcional)", required=False)

    def __init__(self, *args, opciones=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = [(e, Estado(e).label) for e in opciones]


class ResolverForm(forms.Form):
    solucion = forms.CharField(label="Solución aplicada", widget=forms.Textarea(attrs={"rows": 4}))
    minutos = forms.IntegerField(label="Tiempo invertido (minutos)", min_value=0, required=False, initial=0)


class PrioridadForm(forms.Form):
    prioridad = forms.ChoiceField(choices=Prioridad.choices)


class ReprogramarForm(forms.Form):
    fecha = forms.DateField(label="Nueva fecha", input_formats=["%Y-%m-%d"],
                            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    motivo = forms.CharField(label="Motivo (lo verá el solicitante)", max_length=300,
                             widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = timezone.localdate()
        # El navegador solo deja elegir desde mañana hasta el máximo permitido (el servidor lo vuelve a comprobar)
        self.fields["fecha"].widget.attrs.update({
            "min": (hoy + timedelta(days=1)).isoformat(),
            "max": (hoy + timedelta(days=settings.DIAS_MAX_REPROGRAMACION)).isoformat()})


class MotivoForm(forms.Form):
    motivo = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 3}))


class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = ["codigo", "tipo", "marca", "modelo", "serial", "asignado_a", "ubicacion", "observaciones", "activo"]
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asignado_a"].queryset = Usuario.objects.filter(is_active=True)
        self.fields["asignado_a"].required = False
