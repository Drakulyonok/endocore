from endocore.middleware import security_headers_middleware, session_middleware

from settings import SECRET

middlewares = [
    security_headers_middleware(),
    session_middleware(secret=SECRET),
]
