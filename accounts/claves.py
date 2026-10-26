import secrets
MAYUSCULAS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
MINUSCULAS = 'abcdefghijkmnpqrstuvwxyz'
NUMEROS = '23456789'
SIMBOLOS = '!#$%&*-_.?'
TODOS = MAYUSCULAS + MINUSCULAS + NUMEROS + SIMBOLOS

def generar_clave_temporal(largo=12):
    largo = max(largo, 10)
    clave = [secrets.choice(grupo) for grupo in (MAYUSCULAS, MINUSCULAS, NUMEROS, SIMBOLOS)]
    clave += [secrets.choice(TODOS) for _ in range(largo - len(clave))]
    secrets.SystemRandom().shuffle(clave)
    return ''.join(clave)
