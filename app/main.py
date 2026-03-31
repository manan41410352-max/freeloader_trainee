from __future__ import annotations

import argparse

from app.config import load_config
from app.freeloader.workflow import run_workflow
from app.logger import setup_logging


def parse_args() -> argparse.Namespace:
    """Read prompt text from command-line arguments when provided."""
    parser = argparse.ArgumentParser(
        description="Freeloader CLI for local ChatGPT browser automation with Playwright."
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Prompt text. Leave empty to enter the prompt interactively.",
    )
    return parser.parse_args()


def read_prompt(args: argparse.Namespace) -> str:
    """Use CLI arguments first, then fall back to terminal input."""
    if args.prompt:
        return " ".join(args.prompt).strip()
    return input("Enter your prompt: ").strip()


def main() -> int:
    """Command-line entry point for the Freeloader browser workflow."""
    args = parse_args()
    prompt = read_prompt(args)

    if not prompt:
        print("Prompt cannot be empty.")
        return 1

    config = load_config()
    logger = setup_logging(config)

    logger.info("Starting Freeloader browser automation CLI.")
    logger.info("Project root: %s", config.project_root)
    logger.info("Logs file: %s", config.log_file)

    run_workflow(prompt=prompt, config=config, logger=logger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
