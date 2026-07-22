"""GET /v1/purchases — the current user's purchase history."""

from endocore import Depends, Response, require_user_id

from Models.core import Purchase


async def handler(request, user_id=Depends(require_user_id)) -> Response:
    mine = await Purchase.objects.filter(user_id=user_id).select_related("product").alist()
    return Response.json({
        "purchases": [
            {"id": p.pk, "product": p.product.name, "price": p.price}
            for p in mine
        ]
    })
