from django.urls import path

from . import views

app_name = "bitacora"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("matriz.xlsx", views.descargar_matriz, name="matriz"),
    path("nueva/", views.crear, name="crear"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/eliminar/", views.eliminar, name="eliminar"),
]
