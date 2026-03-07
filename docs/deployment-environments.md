# Deployment Environments

OrganicSlides now separates deployment targets into three lanes:

- `development`
  Uses `.env` or `.env.example`, hot reload, mounted source code, and can run with local object storage.
- `staging`
  Uses `.env.staging`, non-reload containers, production-like frontend image, and S3-compatible object storage.
- `production`
  Uses `.env.production`, non-reload containers, stricter config validation, and production-only secrets.

## Compose Usage

Development:

```bash
docker-compose up --build
```

Staging:

```bash
cp .env.staging.example .env.staging
docker-compose -f docker-compose.staging.yml --env-file .env.staging up --build
```

Production:

```bash
cp .env.production.example .env.production
docker-compose -f docker-compose.production.yml --env-file .env.production up --build -d
```

## Config Guardrails

`backend/config.py` enforces:

- `APP_ENV` must be one of `development`, `staging`, `production`
- `DEBUG=false` in `staging` and `production`
- non-default `JWT_SECRET_KEY` in `staging` and `production`
- non-local object storage in `staging` and `production`
