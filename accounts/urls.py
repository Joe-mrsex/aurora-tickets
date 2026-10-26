from django.contrib.auth import views as auth_views
from django.urls import path

from . import segundo_factor, views

app_name = "accounts"

urlpatterns = [
    path("ingresar/", auth_views.LoginView.as_view(template_name="accounts/login.html", redirect_authenticated_user=True), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("tema/", views.cambiar_tema, name="tema"),
    path("cambiar-clave/", views.cambiar_clave, name="cambiar_clave"),
    path("verificar-2fa/", segundo_factor.verificar, name="verificar_2fa"),
    path("activar-2fa/", segundo_factor.activar, name="activar_2fa"),
]
