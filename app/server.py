from __future__ import annotations

from flask import Flask

from app.config import load_config
from app.logger import setup_logging
from app.storage import ChatStore
from app.web import (
    WebServices,
    register_chat_routes,
    register_message_routes,
    register_page_routes,
    register_runtime_routes,
)


def create_app() -> Flask:
    """Create and configure the Freeloader Flask application."""
    config = load_config()
    logger = setup_logging(config)
    store = ChatStore(config.database_path)
    services = WebServices(config=config, logger=logger, store=store)

    flask_app = Flask(
        __name__,
        template_folder=str(config.project_root / "templates"),
        static_folder=str(config.project_root / "static"),
    )
    flask_app.config["APP_CONFIG"] = config
    flask_app.config["APP_LOGGER"] = logger
    flask_app.config["CHAT_STORE"] = store
    flask_app.config["APP_SERVICES"] = services

    register_page_routes(flask_app, services)
    register_chat_routes(flask_app, services)
    register_runtime_routes(flask_app, services)
    register_message_routes(flask_app, services)
    return flask_app


def run_app(flask_app: Flask | None = None) -> None:
    """Run the configured Flask app using the active config."""
    app_instance = flask_app or create_app()
    config = app_instance.config["APP_CONFIG"]
    logger = app_instance.config["APP_LOGGER"]
    logger.info("Starting local web frontend on http://%s:%s", config.web_host, config.web_port)
    app_instance.run(host=config.web_host, port=config.web_port, debug=False, threaded=True)
