"""Middleware registration for the app.

EndoCore reads the ordered ``middlewares`` list below and runs each one inside
the framework's logging middleware. The first entry is the outermost.
"""

from Middleware.request_id import request_id_middleware

# from Middleware.auth import auth_middleware  # enable to require auth globally

middlewares = [
    request_id_middleware,
    # auth_middleware,
]
