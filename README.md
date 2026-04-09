# MorningStar

MorningStar is a full-stack MVP for managing crypto portfolios. The project includes a React + TypeScript frontend, a FastAPI backend, PostgreSQL for persistent data, and an Nginx reverse proxy for edge routing.

## Stack

- Frontend: React, TypeScript, Vite
- Backend: FastAPI, SQLAlchemy
- Database: PostgreSQL 16
- Reverse proxy: Nginx
- Testing: Pytest, Vitest, Playwright
- Delivery: Docker, Docker Compose, GitHub Actions, GHCR

## Container Architecture

The containerized runtime is split into these services:

- `web`: serves the built SPA and proxies `/api`, `robots.txt`, and `sitemap.xml` to the backend.
- `api`: runs FastAPI, performs DB readiness checks at startup, and exposes the application API.
- `db`: PostgreSQL with a persistent named volume.
- `object_storage`: implemented as a persistent Docker volume mounted into the backend container.

Network layout:

- `edge`: public bridge network used by `web` and `api`.
- `backend`: internal bridge network used by `api` and `db`; the database is not exposed publicly.

More details are documented in [docs/lab6-containerization.md](C:/Users/kolya5544/source/repos/MorningStar/docs/lab6-containerization.md).

## Local Run Without Docker

Frontend:

```powershell
cmd /c npm ci
cmd /c npm run dev
```

Backend:

```powershell
python -m pip install -r server\requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir server
```

## Local Run With Docker Compose

1. Create `.env` from [.env.example](C:/Users/kolya5544/source/repos/MorningStar/.env.example).
2. Start the stack:

```powershell
cmd /c docker compose up --build
```

3. Open:

- frontend: `http://localhost:5482`
- backend health: `http://localhost:5482/api/health/`

Stop the stack:

```powershell
cmd /c docker compose down
```

Reset with volumes:

```powershell
cmd /c docker compose down -v
```

## Quality Checks

Backend:

```powershell
pytest
```

Frontend:

```powershell
cmd /c npm run lint
cmd /c npm test
cmd /c npm run test:e2e
```

## Production Deployment

Production deployment files are stored in [deploy/docker-compose.prod.yml](C:/Users/kolya5544/source/repos/MorningStar/deploy/docker-compose.prod.yml) and [deploy/deploy.sh](C:/Users/kolya5544/source/repos/MorningStar/deploy/deploy.sh).

The GitHub Actions workflow:

1. runs linting and all mandatory tests;
2. builds and publishes frontend/backend images to GHCR;
3. copies deployment files to the server;
4. writes the production `.env`;
5. pulls and restarts the stack on the target host.

Required GitHub secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_PATH`
- `PROD_ENV_FILE`

Use [.env.deploy.example](C:/Users/kolya5544/source/repos/MorningStar/.env.deploy.example) as the template for the production environment file kept in `PROD_ENV_FILE`.
