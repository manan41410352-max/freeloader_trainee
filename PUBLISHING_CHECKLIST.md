# Publishing Checklist

Use this before publishing the repository.

## Data and privacy

- Remove or review `data/chats.json`
- Remove or review `data/*.db`
- Review `data/sample_chats.json` and confirm it contains only intentional sample content
- Remove or review `logs/`
- Remove or review `logs/app.log`
- Remove or review `playwright_state/`
- Remove or review `playwright_state/brave_profile/`
- Confirm `.env` is not included

## Documentation

- Confirm `README.md` matches the current feature set
- Confirm `GUIDE.md` still reflects the current doc map and workflow
- Confirm `INSTALLATION.md` still matches the actual setup flow
- Confirm `QUESTIONS.md` answers common open-source questions clearly
- Confirm `PROJECT_STRUCTURE.md` matches the current folder layout

## Legal protection files

- [ ] Added and reviewed `DISCLAIMER.md`
- [ ] Added and reviewed `RESPONSIBLE_USE_AND_COMPLIANCE.md`
- [ ] Added and reviewed `THIRD_PARTY_SERVICES_DISCLAIMER.md`
- [ ] All three files are linked from `README.md`

## Legal and licensing

- Confirm you want to publish under the MIT license in `LICENSE`
- Confirm you are not publishing private prompts, attachments, or output you do not want to share
- Confirm you are not bundling third-party data you lack permission to redistribute
- Confirm the documented third-party-service warnings still match the current services and terms you rely on

## Runtime checks

- Run `python -m compileall web_app.py app`
- Run `node --check static/js/index.js`
- Run `.venv\\Scripts\\python -m pytest -q`
- Start the app and verify `/` loads

## Release hygiene

- Keep generated caches out of the repository
- Keep local-only config paths in `.env.example` generic
- Review requirements files for accuracy
