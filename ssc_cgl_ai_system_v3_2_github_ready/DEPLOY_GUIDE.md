# Beginner Deployment Guide — GitHub → Database → Render

The goal is to stop running the server on the slow PC. The Realme Pad 2 opens the cloud URL in Chrome; the cloud server runs the FastAPI application.

## 1. Put the correct files in GitHub

Upload the **contents** of this V3.2 folder to the repository root.

Your GitHub root must show:

```text
main.py
ai.py
db.py
pipeline.py
requirements.txt
render.yaml
static/
prompts/
```

There should NOT be an `app/` folder for V3.2.

See `GITHUB_UPLOAD_GUIDE.md` for the exact browser-upload procedure.

## 2. Create the database

Create a PostgreSQL database with a provider of your choice. Copy its PostgreSQL connection string and keep it private.

The application creates its tables when it starts, so you do not need to manually create the study tables first.

## 3. Create the Render service

In Render choose **New → Web Service**, connect the GitHub repository, and use:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

The included `render.yaml` contains the same configuration.

Render's FastAPI documentation uses this same Uvicorn pattern for Python web services. See the official Render guide: https://render.com/docs/deploy-fastapi

## 4. Environment variables

Set these in Render:

```text
PYTHON_VERSION=3.13.5
AI_PROVIDER=openai
OPENAI_MODEL=<model available to your account>
OPENAI_API_KEY=<your key>
DATABASE_URL=<your PostgreSQL connection string>
APP_USERNAME=student
APP_PASSWORD=<a strong private password>
```

Never commit your API key or database URL to GitHub.

## 5. Open the app

After deployment, Render gives you an `onrender.com` URL.

Open it on the Realme Pad 2. When Basic Authentication is enabled, use:

```text
Username: student
Password: your APP_PASSWORD
```

Then use Chrome's menu to **Add to Home screen** / **Install app**.

## 6. First functional test

Do not upload your complete study library first.

Use one small topic:

```text
Subject → Topic → one source → Build study pack → 5–10 question test → Submit → Review errors → Flashcards
```

Only after this full loop works should you start importing the rest of your notes.

## 7. Troubleshooting

If Render fails, copy the **first red error block** from the deployment log and send that screenshot/text here.

Never send your `OPENAI_API_KEY` or `DATABASE_URL`.
