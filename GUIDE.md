# Guide

This is the main high-level guide for Freeloader. It points to the single setup guide, the single FAQ, and the legal/compliance docs that matter before use or publication.

## Read in this order

1. [README.md](README.md)
2. [DISCLAIMER.md](DISCLAIMER.md)
3. [RESPONSIBLE_USE_AND_COMPLIANCE.md](RESPONSIBLE_USE_AND_COMPLIANCE.md)
4. [THIRD_PARTY_SERVICES_DISCLAIMER.md](THIRD_PARTY_SERVICES_DISCLAIMER.md)
5. [INSTALLATION.md](INSTALLATION.md)
6. [QUESTIONS.md](QUESTIONS.md)
7. [PUBLISHING_CHECKLIST.md](PUBLISHING_CHECKLIST.md) before any public release

## Canonical docs

- [INSTALLATION.md](INSTALLATION.md): single setup, runtime, testing, and troubleshooting document.
- [QUESTIONS.md](QUESTIONS.md): single FAQ for readers, evaluators, and contributors.
- [GUIDE.md](GUIDE.md): single high-level orientation guide.

Supplemental docs:

- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md): folder and module map.
- [CONTRIBUTING.md](CONTRIBUTING.md): contributor workflow and expectations.
- [LOCAL_MODEL_REQUIREMENTS.txt](LOCAL_MODEL_REQUIREMENTS.txt): technical list of external runtimes and local models.

## What the repository does

Freeloader sends the same prompt to two systems:

- ChatGPT through a Brave browser session controlled by Playwright.
- Ollama through the local Ollama API.

It stores prompts, responses, and hidden preference-style training pairs locally in the repository by default.

## Important legal and compliance note

The ChatGPT browser-automation path is not an official OpenAI integration. Before using it, read [THIRD_PARTY_SERVICES_DISCLAIMER.md](THIRD_PARTY_SERVICES_DISCLAIMER.md) and review the current OpenAI terms that apply to your account and workflow.

## Typical workflow

1. Install Python dependencies and Playwright.
2. Configure `.env`.
3. Start Brave with remote debugging enabled and sign in to ChatGPT yourself.
4. Start Ollama and confirm your selected local model exists.
5. Run the smoke tests.
6. Start the web app.
7. Review stored outputs before sharing, exporting, or publishing them.

## Publishing and contribution expectations

- Keep `.env`, local browser state, logs, and private chat history out of source control.
- Update docs when the setup flow, storage format, runtime dependencies, or legal posture changes.
- Do not contribute features that depend on hidden credentials, bypass technical protections, or encourage policy-violating automation.
- Use [PUBLISHING_CHECKLIST.md](PUBLISHING_CHECKLIST.md) before any release or public upload.

## Public release boundary

For a public repository or release bundle, the safe default is:

- Keep code, templates, static assets, tests, and repository-authored docs.
- Keep `data/sample_chats.json` only if you want a checked-in example dataset for readers.
- Keep placeholder directories such as `data/.gitkeep` and `logs/.gitkeep` only if you want empty folders preserved.
- Exclude local runtime artifacts such as `.env`, `data/chats.json`, `data/*.db`, `logs/app.log`, and `playwright_state/brave_profile/`.

## Repository layout at a glance

- `app/`: Flask app, browser automation, Ollama integration, storage, and speech pipeline.
- `templates/` and `static/`: frontend UI.
- `tests/`: smoke tests.
- `data/`, `logs/`, `playwright_state/`: local runtime state.
