# Project Structure

This document explains the main layout of the Freeloader codebase.

## Top level

- `web_app.py`: minimal web entrypoint
- `GUIDE.md`: main orientation guide
- `DISCLAIMER.md`: general liability and no-warranty notice
- `RESPONSIBLE_USE_AND_COMPLIANCE.md`: user responsibility and acceptable-use boundaries
- `THIRD_PARTY_SERVICES_DISCLAIMER.md`: third-party-service risk notes
- `INSTALLATION.md`: setup and usage guide
- `PROJECT_STRUCTURE.md`: this file
- `README.md`: project overview
- `QUESTIONS.md`: extended Q&A and publishing guidance
- `LOCAL_MODEL_REQUIREMENTS.txt`: external runtime/model dependencies
- `LICENSE`: MIT license for this repository
- `CONTRIBUTING.md`: contributor guidance
- `PUBLISHING_CHECKLIST.md`: release checklist
- `requirements-dev.txt`: development-only test dependency list

- `tests/`
  Smoke tests for the Flask app and publish-time sanity checks.

## App package

- `app/server.py`
  Creates the Flask app and registers routes.

- `app/web/`
  Web-specific modules.
  - `pages.py`: HTML page route
  - `chats.py`: chat history CRUD routes
  - `runtime.py`: warmup and transcription routes
  - `messages.py`: streaming send route
  - `helpers.py`: shared web payload helpers
  - `services.py`: shared config/logger/store container

- `app/freeloader/`
  Browser automation layer for the ChatGPT side.
  - `browser.py`: Brave/CDP connection
  - `page.py`: selector and page target definitions
  - `workflow.py`: prompt send, stream, warmup, and CLI workflow

- `app/storage.py`
  JSON chat storage and DPO-oriented training pair generation.

- `app/ollama_client.py`
  Local Ollama integration.

- `app/speech.py`
  Local Whisper voice transcription.

- `app/attachments.py`
  Attachment extraction and Ollama prompt enrichment.

- `app/config.py`
  Environment loading and shared settings.

- `app/logger.py`
  Logging setup.

## Frontend

- `templates/`
  Jinja templates and partials.

- `static/css/`
  UI styles.

- `static/js/`
  Browser-side chat logic.

## Runtime data

- `data/chats.json`
  Main chat history plus hidden training pairs.

- `data/sample_chats.json`
  Publish-safe example chat history showing the storage format.

- `logs/app.log`
  Runtime logs.
