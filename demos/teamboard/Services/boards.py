"""Board/card access checks and serialization (business logic lives here)."""

from endocore import Forbidden, NotFound

from Models.core import CARD_STATUSES, Board, BoardMember, Card, User


def to_int(value, what: str = "id") -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise NotFound(f"invalid {what}") from None


async def get_board(board_id) -> Board:
    board = await Board.objects.filter(pk=to_int(board_id, "board id")).afirst()
    if board is None:
        raise NotFound("board not found")
    return board


async def require_member(board: Board, user_id: int) -> None:
    is_member = await BoardMember.objects.filter(board=board, user_id=user_id).aexists()
    if not is_member:
        raise Forbidden("not a member of this board")


async def require_owner(board: Board, user_id: int) -> None:
    if board.owner_id != user_id:
        raise Forbidden("owner only")


async def get_card_for(card_id, user_id: int) -> Card:
    card = await Card.objects.filter(pk=to_int(card_id, "card id")).select_related("board").afirst()
    if card is None:
        raise NotFound("card not found")
    await require_member(card.board, user_id)
    return card


def validate_status(status: str) -> str:
    if status not in CARD_STATUSES:
        raise NotFound(f"status must be one of {CARD_STATUSES}")
    return status


def user_dict(user: User) -> dict:
    return {"id": user.pk, "email": user.email, "name": user.name}


def board_dict(board: Board) -> dict:
    return {"id": board.pk, "title": board.title, "owner_id": board.owner_id}


def card_dict(card: Card) -> dict:
    return {
        "id": card.pk,
        "board_id": card.board_id,
        "title": card.title,
        "description": card.description,
        "status": card.status,
        "position": card.position,
        "assignee_id": card.assignee_id,
    }
