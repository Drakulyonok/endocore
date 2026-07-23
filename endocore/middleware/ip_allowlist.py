"""IP allowlist middleware: only accept requests from specific clients.

Restricts by source IP/CIDR range — a header can be spoofed by anyone not
going through a trusted proxy, but the TCP-level source address cannot.
"""

from __future__ import annotations

import ipaddress

from endocore.core.exceptions import Forbidden
from endocore.core.middleware import Next
from endocore.core.request import Request
from endocore.core.response import Response


def ip_allowlist_middleware(*, allowed):
    """``allowed`` is an iterable of IPs and/or CIDR ranges (IPv4 or IPv6),
    e.g. ``["203.0.113.7", "10.0.0.0/24"]``. Put ``proxy_headers_middleware``
    first in the chain if requests arrive through a reverse proxy, otherwise
    every request carries the proxy's own IP instead of the real client's.
    """
    networks = [ipaddress.ip_network(entry, strict=False) for entry in allowed]

    async def middleware(request: Request, call_next: Next) -> Response:
        client = request.scope.get("client")
        ip = client[0] if client else None
        try:
            allowed_ip = ip is not None and any(
                ipaddress.ip_address(ip) in network for network in networks
            )
        except ValueError:
            allowed_ip = False
        if not allowed_ip:
            raise Forbidden("client not allowed")
        return await call_next(request)

    return middleware
