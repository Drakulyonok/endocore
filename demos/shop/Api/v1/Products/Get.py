"""GET /v1/products — the catalogue."""

from endocore import Depends, Response, require_user_id

from Models.core import Product


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    products = await Product.objects.all().alist()
    return Response.json({
        "products": [{"id": p.pk, "name": p.name, "price": p.price} for p in products]
    })
