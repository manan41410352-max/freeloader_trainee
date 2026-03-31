"""Web server modules for the Freeloader desktop interface."""

from .chats import register_chat_routes
from .messages import register_message_routes
from .pages import register_page_routes
from .runtime import register_runtime_routes
from .services import WebServices

__all__ = [
    "WebServices",
    "register_chat_routes",
    "register_message_routes",
    "register_page_routes",
    "register_runtime_routes",
]
