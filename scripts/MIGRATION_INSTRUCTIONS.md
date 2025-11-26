# Migración de Base de Datos - Inicializar Schema

## Problema

La base de datos en producción no existe o no tiene las tablas necesarias, causando errores 500.

## Solución Rápida (RECOMENDADA)

```bash
# En el servidor (ya conectado por SSH)
cd ~/botija
python scripts/init_database.py
pm2 restart all  # o el comando que uses para reiniciar el bot
```

## Opciones Alternativas

### Opción 1: Inicializar base de datos desde cero

```bash
cd ~/botija
# Eliminar DB antigua si existe (PERDERÁS DATOS)
rm -f backend/app.db

# Crear tablas nuevas
python scripts/init_database.py

# Reiniciar aplicación
pm2 restart all
```

### Opción 2: Si ya tienes tabla bot_status pero falta trading_mode

```bash
cd ~/botija
python scripts/migrate_add_trading_mode.py backend/app.db
pm2 restart all
```

## Verificación

Después de migrar, verifica en los logs que no aparezca más el error:

```
no such column: bot_status.trading_mode
```
