from collections import OrderedDict
TEMA_POR_DEFECTO = 'titanio'
TEMAS = OrderedDict([('titanio', {'nombre': 'Titanio', 'descripcion': 'Claro, gris acero y azul hielo', 'fondo': '#E9ECEF', 'primario': '#0369A1', 'acento': '#EA580C'}), ('grafito', {'nombre': 'Grafito', 'descripcion': 'Oscuro minimalista, naranja brasa', 'fondo': '#121214', 'primario': '#FF5A36', 'acento': '#A1A1AA'}), ('neon', {'nombre': 'Neón', 'descripcion': 'Oscuro cyberpunk, cian eléctrico', 'fondo': '#0B0F1A', 'primario': '#22D3EE', 'acento': '#FF9F43'}), ('tinta', {'nombre': 'Tinta', 'descripcion': 'Claro tono papel, azul tinta', 'fondo': '#FAF7F2', 'primario': '#D9381E', 'acento': '#2F4B9A'})])
CHOICES = [(clave, datos['nombre']) for clave, datos in TEMAS.items()]

def tema_valido(valor):
    return valor if isinstance(valor, str) and valor in TEMAS else TEMA_POR_DEFECTO

def lista_para_selector():
    return [dict(clave=clave, **datos) for clave, datos in TEMAS.items()]
