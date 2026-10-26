"""Contraseñas temporales: se entregan a cada persona y se cambian en su primer ingreso."""
import secrets

MAYUSCULAS = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # sin I ni O: se confunden con 1 y 0 al leerlas en un papel
MINUSCULAS = "abcdefghijkmnpqrstuvwxyz"   # sin l ni o
NUMEROS = "23456789"                      # sin 0 ni 1
SIMBOLOS = "!#$%&*-_.?"
TODOS = MAYUSCULAS + MINUSCULAS + NUMEROS + SIMBOLOS


def generar_clave_temporal(largo=12):
    """Aleatoria (módulo `secrets`), de `largo` caracteres y siempre con los cuatro tipos que exige la política."""
    largo = max(largo, 10)
    clave = [secrets.choice(grupo) for grupo in (MAYUSCULAS, MINUSCULAS, NUMEROS, SIMBOLOS)]
    clave += [secrets.choice(TODOS) for _ in range(largo - len(clave))]
    secrets.SystemRandom().shuffle(clave)
    return "".join(clave)
