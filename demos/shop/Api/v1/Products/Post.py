"""POST /v1/products — add a product (any signed-in user in this demo)."""

from endocore import Conflict, Depends, Response, UnprocessableEntity, require_user_id

from Models.core import Product


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    body = await request.json() or {}
    name = (body.get("name") or "").strip()
    try:
        price = int(body.get("price"))
    except (TypeError, ValueError):
        raise UnprocessableEntity("price must be an integer") from None
    if not name or price <= 0:
        raise UnprocessableEntity("name and a positive price are required")
    if await Product.objects.filter(name=name).aexists():
        raise Conflict("product already exists")
    product = await Product.objects.acreate(name=name, price=price)
    return Response.json({"id": product.pk, "name": product.name, "price": product.price},
                         status=201)
