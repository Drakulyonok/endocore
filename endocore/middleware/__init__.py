"""Built-in framework middleware (shipped, not user-authored)."""

from endocore.middleware.cors import cors_middleware
from endocore.middleware.csrf import csrf_middleware
from endocore.middleware.gzip import gzip_middleware
from endocore.middleware.logging import logging_middleware
from endocore.middleware.proxy import proxy_headers_middleware
from endocore.middleware.ratelimit import rate_limit_middleware
from endocore.middleware.security import security_headers_middleware
from endocore.middleware.timeout import timeout_middleware

__all__ = [
    "logging_middleware",
    "cors_middleware",
    "security_headers_middleware",
    "gzip_middleware",
    "proxy_headers_middleware",
    "rate_limit_middleware",
    "timeout_middleware",
    "csrf_middleware",
]
