from django.urls import path
from . import views
app_name = 'tickets'
urlpatterns = [path('', views.lista, name='lista'), path('nuevo/', views.crear, name='crear'), path('<int:pk>/', views.detalle, name='detalle'), path('adjunto/<int:pk>/', views.descargar_adjunto, name='adjunto'), path('equipos/', views.equipos_lista, name='equipos'), path('equipos/nuevo/', views.equipo_form, name='equipo_nuevo'), path('equipos/<int:pk>/', views.equipo_form, name='equipo_editar'), path('equipos/<int:pk>/eliminar/', views.equipo_eliminar, name='equipo_eliminar')]
