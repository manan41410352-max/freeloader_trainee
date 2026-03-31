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

## At A Glance

- Compare hosted and local model answers side by side in one desktop-style web UI.
- Store prompts, responses, and hidden preference pairs locally in a training-friendly JSON format.
- Reuse your own Brave session for the ChatGPT side and your own Ollama models for the local side.
- Warm up the browser, Ollama, and optional voice stack through dedicated runtime endpoints.
- Start with a checked-in publish-safe sample dataset or switch to your own private local history.

## Quick Start

1. Read [GUIDE.md](GUIDE.md) and the legal/compliance docs linked at the top of this page.
2. Follow [INSTALLATION.md](INSTALLATION.md) to create `.venv`, configure `.env`, start Brave with remote debugging, and start Ollama.
3. Run the smoke tests with `.venv\Scripts\python -m pytest -q`.
4. Start the app with `.venv\Scripts\python web_app.py`.
5. Open `http://127.0.0.1:5000`.

For a publish-safe demo run, point `DATABASE_PATH` to `data/sample_chats.json`.

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

## Feature Highlights

- Dual-provider chat flow: the same prompt can be sent to ChatGPT and Ollama at the same time.
- Graceful runtime behavior: if one provider is unavailable, the app can still continue with the other.
- Training-oriented storage: visible chat history plus hidden `training.preference_pairs` in the same JSON store.
- Publish-safe example data: `data/sample_chats.json` gives visitors a safe example of the storage format.
- Local voice path: optional speech-to-text support through a local Whisper-compatible model.
- Small test suite: smoke tests validate the main Flask routes, degraded provider behavior, and runtime warmups.

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

## Runtime Model

Freeloader depends on a few separate moving parts:

- Flask app in this repository
- Brave running locally with remote debugging enabled
- ChatGPT already open in your Brave session
- Ollama running locally with at least one installed model
- optional local Whisper model for voice transcription

If one of those services is unavailable, the corresponding feature will be unavailable too.

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

For a full setup walkthrough, troubleshooting guide, and first-run verification checklist, use [INSTALLATION.md](INSTALLATION.md).

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

## Why Visitors Might Care

- You want a transparent local workspace for comparing hosted and local LLM answers.
- You want to inspect how chat turns and preference-style pairs are stored without digging through a database.
- You want a small Flask + Playwright + Ollama example that is publishable with safe sample data.
- You want a codebase that makes the runtime boundaries and legal boundaries explicit.

## Publishing Notes

Before publishing:

- keep `.env` out of source control
- keep local chat history such as `data/chats.json` and `data/*.db` out of source control unless you intentionally want to share it
- if you keep `data/sample_chats.json`, make sure it remains intentionally publish-safe sample content
- keep `playwright_state/`, including `playwright_state/brave_profile/`, out of source control
- keep `logs/`, including `logs/app.log`, out of source control
- review all stored data for privacy, ownership, and permission before publishing
