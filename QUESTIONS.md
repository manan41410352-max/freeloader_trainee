# Questions And Answers

This file is written for outside readers, contributors, and anyone evaluating the repository before using it.

> IMPORTANT: Before using or publishing, read [DISCLAIMER.md](DISCLAIMER.md), [RESPONSIBLE_USE_AND_COMPLIANCE.md](RESPONSIBLE_USE_AND_COMPLIANCE.md), and [THIRD_PARTY_SERVICES_DISCLAIMER.md](THIRD_PARTY_SERVICES_DISCLAIMER.md).

## What is Freeloader?

Freeloader is a local comparison workspace that sends one prompt to two systems:

- ChatGPT through a Brave browser session controlled by Playwright
- Ollama through the local Ollama API

It stores the resulting conversation in a JSON structure designed to be easier to inspect, compare, and later reuse for custom training workflows.

## Who owns and maintains this repository?

Owner and maintainer: Manan.

## What is the main purpose of the project?

The project exists to help create structured custom comparison data from prompts and responses that the user is allowed to work with.

The design goal is practical:

- compare hosted and local responses
- save the outputs in a reusable format
- support later tuning or preference-style training on custom data

## Is this a general chatbot product?

Not really.

It is better described as a local experimentation and data-building workspace than a polished general-purpose chat product.

## Why store the chats in JSON?

The JSON store makes it easier to:

- inspect the saved data directly
- migrate history without a database tool
- transform the file later into training datasets
- keep a hidden training-oriented preference corpus alongside the visible chat history

## How is each chat turn stored?

Visible turn order is:

1. user prompt
2. ChatGPT response
3. Ollama response

That order is intentional because the repository is built around side-by-side comparison and later preference-style training workflows.

## What hidden training data does the project create?

The main chat file also stores hidden DPO-oriented preference pairs under `training.preference_pairs`.

Each pair is designed around:

- `prompt`
- `chosen` = ChatGPT response
- `rejected` = Ollama response

The UI does not expose that hidden training section directly.

## Where is the chat history stored?

Primary runtime storage is:

- `data/chats.json`

A publish-safe sample dataset is also included at:

- `data/sample_chats.json`

By default, this file is kept out of source control.

## Is the repository self-contained?

Mostly yes.

Inside the repository:

- application code
- templates
- frontend assets
- logs
- browser automation state
- chat storage

Expected dependencies outside the repository are limited to installed software and local models.

## Does the code depend on unrelated folders elsewhere on the device?

No repository code depends on sibling project folders or random local directories.

The only expected external paths are configured tool/model locations, mainly:

- `BRAVE_PATH`
- `WHISPER_MODEL_PATH`

## What software must already exist outside the repository?

At minimum:

- Brave Browser
- Ollama
- one local Ollama model

Optional:

- a local Whisper model for voice transcription

See `LOCAL_MODEL_REQUIREMENTS.txt`.

## Which local model is used by default?

The default local Ollama model is:

- `llama3.1:8b`

That can be changed in `.env`.

## Why does the project use Brave and Playwright?

The ChatGPT side is browser-driven. The repository connects to a user-controlled Brave session through a local CDP endpoint and automates the already logged-in browser context.

That design keeps credentials in the user's own browser profile rather than in the repository.

## Does using the ChatGPT browser automation path raise terms-of-service risk?

Yes.

The official OpenAI Terms of Use published January 1, 2026 prohibit automatic or programmatic extraction of data or output. Based on that language, using Playwright to automate the ChatGPT web interface may violate OpenAI's Terms of Use.

Freeloader is not an official OpenAI integration. It relies on your own logged-in browser session, and you are responsible for deciding whether your intended use is allowed under the current OpenAI terms and any other applicable policies.

## Does this repository include third-party models?

No.

It references external runtimes and locally installed models, but it does not bundle them in the repository.

## Does this repository include my private chat history?

Not unless you intentionally publish it.

The default `.gitignore` excludes:

- `data/chats.json`
- `data/*.db`
- `logs/`
- `playwright_state/`
- `.env`

The checked-in sample file `data/sample_chats.json` is intended to be publish-safe example content, not private runtime history.

## Can I publish my own generated dataset from this project?

That depends on the data, the source material, the platform terms involved, and your legal rights to publish it.

This repository does not decide that for you.

Before publishing any dataset, review:

- privacy
- confidentiality
- copyright
- contractual restrictions
- platform terms
- whether prompts, uploads, or outputs contain sensitive information

## Does the MIT license make the whole workflow legally safe?

No.

The MIT license covers this repository's code and repository-authored documentation only.

It does not automatically grant rights to:

- third-party website content
- service outputs
- uploaded files
- private datasets
- browser session data
- external APIs or services

## Can this repository guarantee freedom from legal or policy risk?

No.

No README, FAQ, or license can guarantee that.

The project tries to reduce obvious avoidable risk by:

- keeping data local by default
- making storage easy to inspect
- not bundling third-party datasets
- leaving account access in the user's own browser session
- documenting responsibility boundaries clearly

## What behavior is not supported or endorsed?

The maintainer does not endorse:

- abusive scraping
- unauthorized data collection
- bypassing authentication, paywalls, or technical protections
- violating third-party terms of service
- using data you do not own or are not allowed to process
- treating this repository as legal advice

## Is the project affiliated with OpenAI, Ollama, Brave, or Hugging Face?

No.

This repository is independent and unofficial.

## What operating environment was this built around?

The current setup and documentation are Windows-first because the local environment and example commands are Windows-oriented.

The Python code itself is largely portable, but the documented setup path is currently centered on Windows usage.

## How do I install it?

Read `INSTALLATION.md`.

That file covers:

- Python environment setup
- Playwright install
- environment variables
- Brave setup
- Ollama setup
- running the web app
- running the CLI mode
- running the tests

## How do I run the tests?

Install development dependencies:

```powershell
pip install -r requirements-dev.txt
```

Then run:

```powershell
.venv\Scripts\python -m pytest -q
```

## What do the checked-in smoke tests actually cover?

The current smoke tests cover:

- Flask app creation
- index page rendering
- chat CRUD endpoints
- the streaming `/api/send` route
- form-post send behavior without files
- warmup routes
- voice transcription route behavior with mocked dependencies

They are intended to catch regressions in repository code, not to prove that every outside dependency is installed and authenticated on every machine.

## What still requires manual verification on a real machine?

The following still depend on a real local environment:

- Brave running with remote debugging enabled
- a live logged-in ChatGPT browser session
- Ollama running locally
- installed local Ollama models
- the optional local Whisper model

## How should issues be reported?

Before opening an issue:

1. read `README.md`
2. read `INSTALLATION.md`
3. read `CONTRIBUTING.md`
4. run the smoke tests
5. include the failing command, error text, and environment details

## What files are most important for new contributors?

- `README.md`
- `INSTALLATION.md`
- `PROJECT_STRUCTURE.md`
- `CONTRIBUTING.md`
- `QUESTIONS.md`

## What files should probably never be committed?

- `.env`
- private `data/chats.json`
- private `data/*.db`
- local `logs/`
- local `playwright_state/`

## Is this repository suitable for people who want a clean base for local data tooling?

Yes, that is one of the main reasons it has been structured this way.

The project is intentionally organized so someone can inspect the storage, route logic, browser automation layer, and UI without hunting across unrelated folders or hidden runtime state.
