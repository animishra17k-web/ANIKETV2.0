# GitHub Upload — V3.2

## IMPORTANT
Upload the **contents of this folder** to the root of your GitHub repository.

After uploading, the GitHub repository root must look like this:

```text
README.md
GITHUB_UPLOAD_GUIDE.md
DEPLOY_GUIDE.md
requirements.txt
render.yaml
Dockerfile
.python-version
main.py
ai.py
db.py
pipeline.py
.env.example
static/
  index.html
  manifest.json
  sw.js
  icons/
    icon-192.png
    icon-512.png
prompts/
  README.md
  system.md
```

Do NOT create or upload an `app/` folder for this version.

Do NOT upload `.env`, `.venv`, `data/`, or `exports/`.

## GitHub browser upload

1. Open the repository.
2. Click **Add file → Upload files**.
3. Open this V3.2 folder on the computer.
4. Select the files and folders shown above.
5. Drag them into the GitHub upload area.
6. Before committing, verify that `main.py` is visible at the repository root and that `static` and `prompts` appear as folders.
7. Commit the changes.

The deployment command for this version is:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```
