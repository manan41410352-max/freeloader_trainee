# Freeloader Dual Chat Desktop

> IMPORTANT: Before using or publishing, read [DISCLAIMER.md](DISCLAIMER.md), [RESPONSIBLE_USE_AND_COMPLIANCE.md](RESPONSIBLE_USE_AND_COMPLIANCE.md), and [THIRD_PARTY_SERVICES_DISCLAIMER.md](THIRD_PARTY_SERVICES_DISCLAIMER.md).
>
> Start with [GUIDE.md](GUIDE.md), then use [INSTALLATION.md](INSTALLATION.md) for setup and [QUESTIONS.md](QUESTIONS.md) for the full FAQ.

Owner and maintainer: Manan

License: MIT. See `LICENSE`.

Freeloader is a local comparison workspace for building custom training data from side-by-side responses.
It sends the same prompt to:

- ChatGPT through a Brave browser session controlled by Playwright
- Ollama through the local Ollama API

The project is designed to help the owner create structured custom data for later model training and evaluation on data they control or are authorized to use.

## Purpose

- Compare hosted and local responses in one interface
- Save prompts and replies in a JSON format that is easier to reuse for training
- Build hidden DPO-style preference pairs where:
  - `chosen` = ChatGPT response
  - `rejected` = Ollama response
- Keep project-generated data local to this repository by default

## Local-First Design

This repository is intentionally self-contained for code, UI, logs, and runtime state.

Inside the project folder:

- `app/`
- `templates/`
- `static/`
- `data/`
- `logs/`
- `playwright_state/`

Expected external dependencies:

- Brave installation
- Ollama installation and at least one local Ollama model
- Optional local Whisper model for voice transcription

See `LOCAL_MODEL_REQUIREMENTS.txt` for the external runtime/model list.

## Legal And Usage Boundaries

This repository is written to reduce avoidable risk, but it cannot guarantee freedom from legal claims, policy issues, or terms-of-service problems.

Read these documents before use:

- `DISCLAIMER.md`
- `RESPONSIBLE_USE_AND_COMPLIANCE.md`
- `THIRD_PARTY_SERVICES_DISCLAIMER.md`

Important specific risk:

- The official OpenAI Terms of Use published January 1, 2026 include a restriction on automatic or programmatic extraction of data or output.
- Because Freeloader can automate the ChatGPT web interface through Brave plus Playwright, that workflow may violate OpenAI's Terms of Use depending on how you use it.
- Review the current official terms before enabling that part of the project.

Use it only if you are comfortable taking responsibility for:

- the data you process
- the services you connect to
- the model outputs you store
- the laws and platform terms that apply to you

Important boundaries:

- Use only data you own, created, or are authorized to process.
- Do not use the project to bypass authentication, paywalls, rate limits, or technical protections.
- Do not assume the MIT license gives rights to third-party content, model outputs, websites, or service APIs.
- Do not treat this repository as legal advice.

The maintainer does not endorse abusive scraping, unauthorized data collection, or misuse of third-party services.

## Non-Affiliation

This project is not affiliated with, endorsed by, or sponsored by OpenAI, Ollama, Brave, Hugging Face, or any model provider referenced by the codebase.

## Project Docs

- `GUIDE.md`: main orientation guide and reading order
- `DISCLAIMER.md`: general liability and no-warranty notice
- `RESPONSIBLE_USE_AND_COMPLIANCE.md`: user responsibility and acceptable-use boundaries
- `THIRD_PARTY_SERVICES_DISCLAIMER.md`: third-party-service risk notes, including the ChatGPT browser-automation boundary
- `INSTALLATION.md`: setup and usage
- `PROJECT_STRUCTURE.md`: codebase layout
- `QUESTIONS.md`: detailed Q&A about intent, storage, scope, safety, and publishing
- `LOCAL_MODEL_REQUIREMENTS.txt`: external runtime/model requirements
- `CONTRIBUTING.md`: contributor workflow and test expectations
- `PUBLISHING_CHECKLIST.md`: pre-release sanity checklist

## Main Entrypoints

- Web UI: `python web_app.py`
- CLI browser workflow: `python -m app.main "your prompt"`

## Development And Testing

Development-only dependencies live in `requirements-dev.txt`.

Run the smoke tests with:

```powershell
.venv\Scripts\python -m pytest -q
```

The current smoke suite checks the Flask app, chat routes, send route, warmup routes, and mocked transcription flow.

## Chat Storage

Primary chat history is stored in `data/chats.json`.

A checked-in publish-safe sample dataset is also included at `data/sample_chats.json`.

Visible turn order:

1. User prompt
2. ChatGPT response
3. Ollama response

Hidden training data:

- `training.preference_pairs`
- `chosen`: ChatGPT response
- `rejected`: Ollama response

These training fields are not shown in the UI.

If you want to launch the app against the sample dataset instead of your own local history, point `DATABASE_PATH` to `data/sample_chats.json`.

## Publishing Notes

Before publishing:

- keep `.env` out of source control
- keep local chat history such as `data/chats.json` and `data/*.db` out of source control unless you intentionally want to share it
- if you keep `data/sample_chats.json`, make sure it remains intentionally publish-safe sample content
- keep `playwright_state/`, including `playwright_state/brave_profile/`, out of source control
- keep `logs/`, including `logs/app.log`, out of source control
- review all stored data for privacy, ownership, and permission before publishing
