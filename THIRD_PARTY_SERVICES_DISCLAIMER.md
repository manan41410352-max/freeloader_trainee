# Third-Party Services Disclaimer

Freeloader can interact with third-party services and software in the following ways:

1. ChatGPT through a user-controlled Brave browser session automated with Playwright.
2. Ollama through the local Ollama API and locally installed models.
3. Brave Browser through a local CDP remote-debugging connection.

## OpenAI and ChatGPT

The official OpenAI [Terms of Use](https://openai.com/policies/terms-of-use/) published January 1, 2026 state that users may not "Automatically or programmatically extract data or Output."

Based on that language, using Playwright or similar tooling to automate the ChatGPT web interface may violate OpenAI's Terms of Use.

Freeloader is not an official OpenAI integration. It does not provide API keys, authentication bypasses, rate-limit bypasses, or any claim of permission from OpenAI. It relies entirely on your own logged-in browser session. You must review the current OpenAI terms and decide for yourself whether any planned use is allowed.

## Ollama and local models

You are responsible for complying with:

- Ollama's own terms, licenses, and distribution rules.
- The license and usage restrictions of every local model you install or run.
- Any downstream obligations attached to locally generated outputs.

## Brave Browser and remote debugging

You must configure Brave remote debugging yourself and use only browser profiles, sessions, accounts, and data that you are authorized to control.

## Non-affiliation

This repository is not affiliated with, endorsed by, or sponsored by OpenAI, Ollama, Brave Software, Anthropic, Hugging Face, or any model provider referenced in the code or docs. All trademarks and service marks remain the property of their respective owners.

## No endorsement of policy violations

The maintainer does not endorse, encourage, or support any use of Freeloader that violates the rules of a third-party platform. The existence of browser automation code in this repository is not permission, advice, or approval to violate any service's terms.

## Data ownership and publication risk

You are solely responsible for the legality, ownership, privacy review, and publication rights of any prompts, attachments, outputs, training pairs, or datasets produced with this repository.

If you cannot accept these conditions, do not use or publish this repository.
