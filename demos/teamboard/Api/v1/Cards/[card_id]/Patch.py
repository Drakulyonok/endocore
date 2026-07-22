"""PATCH /v1/cards/{card_id} — move/edit a card and notify the room."""

from endocore import Depends, NotFound, Response, require_user_id

from Models.core import User
from Services.boards import card_dict, get_card_for, validate_status
from Services.live import broadcast


async def handler(request, card_id, user_id=Depends(require_user_id)) -> Response:
    card = await get_card_for(card_id, user_id)
    body = await request.json() or {}

    if "title" in body and (body["title"] or "").strip():
        card.title = body["title"].strip()
    if "description" in body:
        card.description = body["description"] or ""
    if "status" in body:
        card.status = validate_status(body["status"])
    if "position" in body:
        card.position = int(body["position"])
    if "assignee_id" in body:
        assignee_id = body["assignee_id"]
        if assignee_id is not None and not await User.objects.filter(pk=assignee_id).aexists():
            raise NotFound("assignee not found")
        card.assignee_id = assignee_id

    await card.asave()
    await broadcast("card.updated", card.board_id, {"card": card_dict(card)})
    return Response.json(card_dict(card))
