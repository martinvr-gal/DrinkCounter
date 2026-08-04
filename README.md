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
El contador se conserva por separado en SQLite, en `./counter-data/counter.db`; los clips de vídeo se sirven desde `./clips`.

## Funciones adicionales del backend

- `GET /api/counter` permite consultar el contador. Sus cambios (`increment`, `decrement` y `set`) requieren un JWT de administrador.
- Spotify se configura mediante `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` y `SPOTIFY_DEFAULT_PLAYLIST`. Inicia su autorización en `GET /admin/spotify/login` con JWT; la sesión se conserva temporalmente en memoria del backend.
- `GET /api/clips` lista los vídeos disponibles y `GET /clips/{archivo}` los sirve. Se admiten `.mp4`, `.webm`, `.mov` y `.m4v`.

## Decisiones de arquitectura

- Las transiciones de estado usan una versión en la fila para impedir que dos administradores revisen la misma foto simultáneamente.
- El sistema de ficheros está aislado tras la interfaz `Storage`; se puede incorporar un adaptador S3 sin cambiar los endpoints.
- Un WebSocket emite los cambios de fotografías para mantener sincronizados los televisores y las sesiones de administración.
- La API valida MIME, tamaño, nombre y acceso administrativo mediante JWT.
- La galería y el contador usan bases de datos independientes: PostgreSQL y SQLite, respectivamente.

Para producción, configura `CORS_ORIGINS`, credenciales seguras, TLS mediante un proxy inverso y ejecuta las migraciones Alembic como parte del despliegue.
