# SSC CGL AI Preparation OS — V3.2 GitHub-Ready

A cloud-ready, layered AI study system for SSC CGL preparation.

## What V3.2 fixes

- Flat GitHub-friendly repository: no required `app/` package.
- Render starts the service with `uvicorn main:app`.
- FastAPI static assets and PWA files are served correctly.
- Local authentication stays open when `APP_PASSWORD` is blank.
- Public deployments can enable HTTP Basic authentication with `APP_USERNAME` and `APP_PASSWORD`.
- Test scores are calculated deterministically from stored answers; AI is used for error analysis.
- PDF export escapes study content before inserting it into ReportLab paragraphs.
- SQLite works locally; PostgreSQL is used when `DATABASE_URL` is provided.
- Python runtime is pinned to 3.13.5 for reproducible Render deployment.

## Architecture

```text
SOURCE
  ↓
EXTRACT → TEACH → FLASHCARD → QUESTION → VALIDATE
                                      ↓
                                    TEST
                                      ↓
                                  EVALUATE
                                      ↓
                              WEAKNESS / REVIEW
```

The supplied study sources are treated as primary authority. AI-generated material is a derived artifact and should remain traceable to the source.

## Cloud deployment

Recommended personal setup:

```text
GitHub → Render → PostgreSQL database → AI provider
                         ↑
                    Realme Pad 2
```

See `DEPLOY_GUIDE.md` and `GITHUB_UPLOAD_GUIDE.md`.
