# Installation And Usage

This is the detailed setup guide for running Freeloader locally on Windows.

> IMPORTANT: Before enabling browser automation or publishing anything from this repository, read [DISCLAIMER.md](DISCLAIMER.md), [RESPONSIBLE_USE_AND_COMPLIANCE.md](RESPONSIBLE_USE_AND_COMPLIANCE.md), and [THIRD_PARTY_SERVICES_DISCLAIMER.md](THIRD_PARTY_SERVICES_DISCLAIMER.md).

## What this guide covers

This file explains:

- what must already be installed on your machine
- how to create the Python environment
- how to configure `.env`
- how to start Brave, ChatGPT, and Ollama correctly
- how to run the web UI and optional CLI mode
- how to use the included sample dataset
- how to verify that the real local runtime is working
- what to check when something fails

This is a technical setup guide only. It does not give you permission to use any third-party service.

## Important legal note before setup

The ChatGPT browser-automation path is not an official OpenAI integration. The official OpenAI Terms of Use published January 1, 2026 include a restriction on automatic or programmatic extraction of data or output, so you must review the current terms and decide for yourself whether your intended use is allowed before enabling that workflow.

## Runtime overview

Freeloader has three major runtime pieces:

1. The Flask web app in this repository.
2. A Brave browser session with remote debugging enabled and ChatGPT already open in that browser.
3. A local Ollama server with at least one installed model.

Optional:

4. A local Whisper-compatible voice model for transcription.

If any one of those pieces is missing, the corresponding feature will not work.

## Prerequisites

Minimum practical setup:

- Windows
- Python 3.11 or newer
- Brave Browser installed
- Ollama installed
- At least one Ollama model such as `llama3.1:8b`

Optional:

- A local Whisper model at `WHISPER_MODEL_PATH`

See [LOCAL_MODEL_REQUIREMENTS.txt](LOCAL_MODEL_REQUIREMENTS.txt) for the external runtime and model list.

## Repository-local runtime state

By default, the repository keeps its own runtime data inside the project folder:

- `data/`: chat history and sample data
- `logs/`: application logs
- `playwright_state/`: local browser automation state

Default live storage file:

- `data/chats.json`

Included checked-in sample dataset:

- `data/sample_chats.json`

## 1. Open the project folder

From PowerShell, move into the repository root:

```powershell
cd C:\Users\Asus\OneDrive\Desktop\project_api
```

Everything in the rest of this guide assumes you are running commands from the repository root.

## 2. Create the virtual environment

Create a local Python virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, you can either open PowerShell with an execution policy that allows local activation or use the full Python path without activation:

```powershell
.venv\Scripts\python --version
```

## 3. Install Python dependencies

Install the main runtime dependencies:

```powershell
pip install -r requirements.txt
```

Install the Playwright browser runtime used by the browser automation layer:

```powershell
python -m playwright install chromium
```

If you want to run the smoke tests too, install development dependencies:

```powershell
pip install -r requirements-dev.txt
```

## 4. Create and review `.env`

Copy the example file:

```powershell
Copy-Item .env.example .env
```

Then open `.env` and review the values.

### Key settings

`BRAVE_PATH`
: Full path to your Brave executable.

`CDP_ENDPOINT`
: Local remote-debugging endpoint. Default is `http://127.0.0.1:9222`.

`DEFAULT_OLLAMA_MODEL`
: The Ollama model the UI should prefer by default.

`DATABASE_PATH`
: The chat storage file the app should read and write.

`WHISPER_MODEL_PATH`
: Optional local voice-model path.

`WEB_HOST` and `WEB_PORT`
: Where the Flask app should listen.

### Default values in `.env.example`

The default example is already set up for the normal local path:

- `DATABASE_PATH=data/chats.json`
- `LOG_FILE=logs/app.log`
- `USER_DATA_DIR=playwright_state/brave_profile`

### Use the sample dataset

If you want the app to start with the checked-in sample data instead of your own live chat file, change:

```text
DATABASE_PATH=data/chats.json
```

to:

```text
DATABASE_PATH=data/sample_chats.json
```

That is useful for:

- demos
- screenshots
- public repository review
- starting from a known safe sample file

If you use the sample file as the live database, new chats will be written back into that sample file. For your own normal use, switch back to `data/chats.json`.

## 5. Start Brave with remote debugging

Close every open Brave window first. Then launch Brave manually with remote debugging enabled:

```powershell
"& 'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe' --remote-debugging-port=9222"
```

What this does:

- starts Brave normally
- exposes a local CDP debugging endpoint on port `9222`
- allows Playwright to attach to your already-running browser session

After Brave opens:

1. open `https://chatgpt.com/`
2. sign in manually if needed
3. leave the tab open

Freeloader does not log you in for you. It expects ChatGPT to already be available in your own Brave session.

## 6. Start Ollama and verify the model

In a separate terminal, start the local Ollama service if it is not already running:

```powershell
ollama serve
```

In another terminal, verify that Ollama responds:

```powershell
ollama list
```

If you do not yet have the default model, pull it:

```powershell
ollama pull llama3.1:8b
```

You can use another local model if you prefer, but then you should also update `DEFAULT_OLLAMA_MODEL` in `.env`.

## 7. Optional voice setup

Voice input is optional.

If you want local voice transcription:

1. install the required Python packages from `requirements.txt`
2. download or place your local voice model
3. make sure `.env` points `WHISPER_MODEL_PATH` to the correct folder

Expected default location:

```text
~/.ollama/models/external/Oriserve-Whisper-Hindi2Hinglish-Apex
```

If the voice model is missing or blocked by system policy, the main chat app can still run. Only the voice warmup and transcription route will fail.

## 8. Run the smoke tests

If you installed `requirements-dev.txt`, run:

```powershell
.venv\Scripts\python -m pytest -q
```

What the smoke tests cover:

- Flask app creation
- index page rendering
- chat CRUD routes
- dual-provider send route behavior
- degraded send behavior when only one provider is available
- warmup endpoints
- transcription route with mocked speech dependencies

The smoke tests validate repository code. They do not prove that your local Brave session, ChatGPT login, Ollama service, or voice model are configured correctly on your machine.

## 9. Run the web app

Start the Flask app:

```powershell
.venv\Scripts\python web_app.py
```

Then open:

```text
http://127.0.0.1:5000
```

What you should see:

- the page loads
- ChatGPT status shows whether Brave is attached
- Ollama status shows whether local models were found
- the composer is enabled

## 10. Optional CLI mode

You can also use the browser workflow from the terminal without the web UI:

```powershell
.venv\Scripts\python -m app.main "Explain transformer attention simply"
```

This path still depends on:

- Brave running with remote debugging
- ChatGPT already open and logged in

## 11. First-run verification

Once the app is open in the browser, verify the system in this order.

### A. Browser side

- Brave is open
- ChatGPT is open in Brave
- you are logged in
- no modal, verification challenge, or blocked page is covering the chat input

### B. Ollama side

- `ollama serve` is running
- `ollama list` shows the model you want
- the selected model appears in the app UI

### C. App side

Send a simple prompt such as:

```text
Reply with exactly LOCAL_SMOKE_OK
```

Expected result:

- ChatGPT should produce `LOCAL_SMOKE_OK`
- Ollama should produce some response, ideally also `LOCAL_SMOKE_OK`
- the turn should be saved into the active database file

## 12. Programmatic warmup checks

You can verify the warmup endpoints directly from Python:

```powershell
@'
from web_app import app
client = app.test_client()
print(client.post('/api/browser/warmup').status_code)
print(client.post('/api/ollama/warmup', json={'model': 'llama3.1:8b'}).status_code)
print(client.post('/api/transcribe/warmup').status_code)
'@ | .venv\Scripts\python -
```

Typical expected results:

- browser warmup: `200` if Brave is running and ChatGPT is reachable
- Ollama warmup: `200` if Ollama is running and the model exists
- voice warmup: `200` if the local voice stack is available, otherwise `503`

## 13. Running against the sample dataset

To run a clean demo against the checked-in sample data:

1. set `DATABASE_PATH=data/sample_chats.json` in `.env`
2. start the app
3. open the UI
4. confirm that sample chats appear

This is useful for:

- publishing screenshots
- sharing the repository with visible example content
- reviewing the JSON storage format without exposing private chats

## 14. Common issues

- `Brave is not exposing remote debugging on port 9222`
  Start Brave with `--remote-debugging-port=9222` and close older Brave windows first.

- `No local models found`
  Make sure `ollama serve` is running and the configured model exists.

- `Ollama model '...' is not installed`
  Pull that model with `ollama pull ...` or change `DEFAULT_OLLAMA_MODEL`.

- `ChatGPT input box is not visible`
  Open ChatGPT in Brave, sign in, and clear any modal or verification screen.

- `Voice transcription is unavailable because the local speech dependencies could not be imported`
  Reinstall dependencies from `requirements.txt` and confirm your Python environment is healthy.

- `DLL load failed while importing _multiarray_umath: An Application Control policy has blocked this file`
  This is a Windows AppLocker or WDAC policy issue blocking NumPy or Torch. The app can still start, but voice warmup and transcription will return `503` until the policy allows those DLLs or the Python environment is moved to an approved location.

- the sample data does not appear
  Confirm `DATABASE_PATH` points to `data/sample_chats.json` and restart the app process.

## 15. Responsible use reminder

- Use only accounts and data you are authorized to use.
- Review service terms before connecting browser automation to third-party services.
- Review generated training data before publishing, sharing, or fine-tuning on it.

For the repository's legal and compliance baseline, read:

- `DISCLAIMER.md`
- `RESPONSIBLE_USE_AND_COMPLIANCE.md`
- `THIRD_PARTY_SERVICES_DISCLAIMER.md`
