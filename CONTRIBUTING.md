# Contributing

Thanks for taking interest in Freeloader.

## Before you open an issue

- Read `README.md`
- Read `GUIDE.md`
- Read `DISCLAIMER.md`
- Read `RESPONSIBLE_USE_AND_COMPLIANCE.md`
- Read `THIRD_PARTY_SERVICES_DISCLAIMER.md`
- Read `INSTALLATION.md`
- Read `QUESTIONS.md`
- Run the local test suite

## Development setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m playwright install chromium
```

## Run the app

```powershell
.venv\Scripts\python web_app.py
```

## Run the tests

```powershell
.venv\Scripts\python -m pytest -q
```

## Contribution guidelines

- Keep changes local-first and transparent.
- Do not add hidden network dependencies.
- Do not commit `.env`, local chat history, logs, or browser session state.
- Prefer small, focused pull requests.
- Include or update tests when changing runtime behavior.
- Update docs when changing setup, environment variables, or storage format.

## Scope notes

Freeloader is meant to help compare responses and build structured custom datasets from data the user controls or is authorized to use.

Contributions that encourage unauthorized access, abusive automation, or unsafe data handling are not welcome.

Contributions that attempt to normalize or conceal third-party terms-of-service violations are also not welcome.
