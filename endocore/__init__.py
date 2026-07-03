"""EndoCore — file-based ASGI backend framework.

Public API surface. User handlers import from here:

    from endocore import Request, Response
"""

from endocore.core.application import Application
from endocore.core.cache import cached, configure_cache, get_cache
from endocore.core.config import Settings, env, load_dotenv
from endocore.core.datastructures import FormData, QueryParams, UploadFile
from endocore.core.di import Depends
from endocore.core.exceptions import (
    BadRequest,
    Conflict,
    Forbidden,
    HTTPError,
    MethodNotAllowed,
    NotFound,
    PayloadTooLarge,
    PermissionDenied,
    TooManyRequests,
    Unauthorized,
    UnprocessableEntity,
)
from endocore.core.request import Request
from endocore.core.response import Response, StreamingResponse
from endocore.core.websocket import WebSocket, WebSocketDisconnect
from endocore.core.pubsub import WebSocketManager
from endocore.core.logging import get_logger

__version__ = "0.6.0b1"

__all__ = [
    "Application",
    "Request",
    "Response",
    "StreamingResponse",
    "WebSocket",
    "WebSocketDisconnect",
    "WebSocketManager",
    "UploadFile",
    "FormData",
    "QueryParams",
    "Depends",
    "Settings",
    "env",
    "load_dotenv",
    "get_cache",
    "configure_cache",
    "cached",
    "get_logger",
    # HTTP exceptions
    "HTTPError",
    "BadRequest",
    "Unauthorized",
    "Forbidden",
    "PermissionDenied",
    "NotFound",
    "MethodNotAllowed",
    "Conflict",
    "PayloadTooLarge",
    "UnprocessableEntity",
    "TooManyRequests",
    "__version__",
]
