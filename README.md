# SmartCuts

SaaS que convierte vídeos largos en clips verticales listos para TikTok, Reels y
Shorts: transcribe, elige los mejores momentos con Claude, reencuadra a 9:16
siguiendo la cara y añade subtítulos con la palabra activa resaltada.

> Versión comercial: los usuarios **suben sus propios archivos**. No hay
> descarga desde YouTube ni otras plataformas (la versión de uso personal con
> YouTube vive en `../SmartCuts-Personal`).

## Arquitectura

```
Next.js (web/) ──JWT──▶ FastAPI (api) ──SQL──▶ Postgres ◀── worker (GPU) = core SmartCuts
     │  polling /jobs/:id        │ URLs firmadas              │ sube clips
     └──── subida/descarga directa ───────▶ Cloudflare R2 ◀───┘
```

- **web/**: Next.js + TypeScript + Tailwind + shadcn/ui + TanStack Query. Tipos de la API generados desde OpenAPI.
- **API** (`src/smartcuts/interfaces/api`): FastAPI sin estado. Auth (Supabase JWT), cuotas, jobs, URLs firmadas.
- **Dominio SaaS** (`src/smartcuts/saas`): usuarios, planes, subidas, jobs, clips y libro de consumo en minutos.
- **Worker** (`src/smartcuts/saas/worker.py`): reclama jobs de la tabla `jobs` (cola en Postgres), ejecuta el core,
  informa del progreso con latido, sube resultados y devuelve los minutos si algo falla.
- **Core** (`src/smartcuts/{domain,application,adapters,infra}`): el pipeline de vídeo, sin cambios de diseño.

| Entorno | BD | Auth | Almacenamiento | Worker | LLM |
|---|---|---|---|---|---|
| dev | SQLite (`data/`) | `dev` (email sin contraseña) | disco (`data/storage`) | local (tu GPU) | tu suscripción (`claude_cli`) o API |
| prod (UE) | Supabase Postgres | Supabase Auth | Cloudflare R2 (jurisdicción EU) | Modal (GPU T4, región UE) | API de Anthropic |

La configuración de producción se valida al arrancar: rechaza clave por defecto, auth `dev`, SQLite,
almacenamiento local o el proveedor `claude_cli`.

## Desarrollo local

Requisitos: Python 3.12, Node 20+, ffmpeg en el PATH. GPU NVIDIA opcional (Whisper en CUDA).

```powershell
# una vez
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[gpu,dev]"
copy .env.example .env
cd web; npm install; copy .env.example .env.local; cd ..

# tres terminales (o todo de golpe: doble clic en dev.cmd)
.venv\Scripts\smartcuts api --reload     # http://localhost:8000  (docs en /docs)
.venv\Scripts\smartcuts worker
cd web; npm run dev                      # http://localhost:3000
```

Otros comandos:

```powershell
.venv\Scripts\smartcuts doctor           # comprueba el entorno
.venv\Scripts\smartcuts db-upgrade       # aplica migraciones (en dev se aplican solas)
.venv\Scripts\smartcuts openapi; cd web; npm run gen:api   # regenera los tipos del frontend
.venv\Scripts\smartcuts process video.mp4 -n 5              # usar el core sin web
```

Cambiar el modelo de datos: edita `src/smartcuts/saas/models.py` y genera la migración con
`python -c "from smartcuts.infra.config import Settings; from smartcuts.saas.migrations import make_migration; make_migration(Settings(), 'descripcion')"`.

## Worker en Modal

Cada vídeo arranca una GPU en Modal (`deploy/modal_app.py`) que solo cuesta mientras procesa. La imagen lleva
ya dentro ffmpeg, el modelo de Whisper, el detector de caras y la fuente de los subtítulos. Dos tareas
programadas cubren los fallos: cada 5 min se reenvían los jobs que no arrancaron o cuyo worker murió, y cada
hora se ejecuta la limpieza (caducidad, subidas abandonadas).

```powershell
.venv\Scripts\python -m pip install -e ".[modal]"
.venv\Scripts\python deploy\modal_cli.py token new             # una vez: vincula tu cuenta de Modal
.venv\Scripts\python deploy\modal_secret.py                    # copia la config de prod desde .env al secreto de Modal
.venv\Scripts\python deploy\modal_cli.py run deploy/modal_app.py::smoke   # diagnóstico de la imagen con GPU
.venv\Scripts\python deploy\modal_cli.py deploy deploy/modal_app.py       # publica (repetir tras cada cambio del core)
```

`deploy/modal_cli.py` es la CLI de `modal` usando los certificados de Windows (necesario si un antivirus
inspecciona HTTPS). Para que la API envíe los vídeos a Modal: `SMARTCUTS_WORKER__DISPATCHER=modal` en su
entorno; con eso `dev.cmd` ya no abre el worker local.

## Planes y consumo

Se mide en **minutos de vídeo** (redondeados a la décima). Al encolar un vídeo se reservan sus
minutos; si el procesamiento falla se devuelven automáticamente. Catálogo en
`src/smartcuts/saas/plans.py` (precios provisionales; `stripe_price_id` listo para la fase de cobros).

## Tests

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check src tests migrations
cd web; npm run typecheck; npm run lint
```
