# Galería de fotografías

Aplicación React + FastAPI para recepción, moderación y presentación de fotos en televisión.

## Arranque

1. Copia las variables: `cp .env.example .env`.
2. Cambia al menos `JWT_SECRET` y las credenciales de administrador.
3. Ejecuta `docker compose up --build`.

Servicios:

- Usuario: http://localhost:5173/
- Administración: http://localhost:5173/admin
- Televisión: http://localhost:5173/tv
- API: http://localhost:8000/docs

Las fotos se persisten en `./uploads/{pending,approved,rejected}` y PostgreSQL en el volumen Docker.

## Decisiones de arquitectura

- Las transiciones de estado usan una versión en la fila para impedir que dos administradores revisen la misma foto simultáneamente.
- El sistema de ficheros está aislado tras la interfaz `Storage`; se puede incorporar un adaptador S3 sin cambiar los endpoints.
- Un WebSocket emite los cambios de fotografías para mantener sincronizados los televisores y las sesiones de administración.
- La API valida MIME, tamaño, nombre y acceso administrativo mediante JWT.

Para producción, configura `CORS_ORIGINS`, credenciales seguras, TLS mediante un proxy inverso y ejecuta las migraciones Alembic como parte del despliegue.
