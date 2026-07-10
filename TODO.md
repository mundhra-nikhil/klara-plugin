# TODO — Known Gaps

- [ ] **CI is frontend-only** — no Python lint/test, no Docker image build, no CD pipeline
- [ ] **No production runtime config** — no gunicorn workers, no nginx, no TLS termination, no docker-compose.prod.yml
- [ ] **Qdrant has no healthcheck** in docker-compose (unlike Postgres/Redis)
- [ ] **No reverse proxy** — backend uvicorn and frontend webpack-dev-server exposed directly
- [ ] **Chat is stubbed** — both frontend (`ChatInput.tsx`) and backend (`/documents/:id/chat`) are placeholder
