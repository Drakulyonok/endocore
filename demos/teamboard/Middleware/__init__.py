from endocore.middleware import (
    rate_limit_middleware,
    security_headers_middleware,
    session_middleware,
)

from settings import SECRET

middlewares = [
    security_headers_middleware(),
    rate_limit_middleware(limit=300, window=60),
    session_middleware(secret=SECRET),
]
