import logging
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from accounts.context_processors import VERSION
logger = logging.getLogger('tickets')

@require_GET
def salud(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        ejecutor = MigrationExecutor(connection)
        pendientes = bool(ejecutor.migration_plan(ejecutor.loader.graph.leaf_nodes()))
    except Exception:
        logger.exception('Comprobación de salud: la base de datos no responde')
        return JsonResponse({'estado': 'error', 'motivo': 'base_de_datos'}, status=503)
    if pendientes:
        return JsonResponse({'estado': 'migraciones_pendientes'}, status=503)
    return JsonResponse({'estado': 'ok', 'version': VERSION})
