from __future__ import annotations

from flask import Flask, render_template

from app.web.helpers import build_shell_payload
from app.web.services import WebServices


def register_page_routes(flask_app: Flask, services: WebServices) -> None:
    """Register the HTML page routes for the desktop chat UI."""

    @flask_app.get("/")
    def index() -> str:
        return render_template("index.html", initial_shell=build_shell_payload(services))
