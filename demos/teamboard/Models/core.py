"""TeamBoard data model: users, boards, membership, cards."""

from endocore.orm import Model, configure, fields

from settings import DATABASE

configure(backend="sqlite", database=DATABASE)

CARD_STATUSES = ("todo", "doing", "done")


class User(Model):
    class Meta:
        table = "tb_users"

    email = fields.CharField(max_length=120, unique=True)
    name = fields.CharField(max_length=80)
    password_hash = fields.CharField(max_length=200)
    created = fields.DateTimeField(auto_now_add=True)


class Board(Model):
    class Meta:
        table = "tb_boards"
        ordering = ["id"]

    owner = fields.ForeignKey(User, on_delete="CASCADE")
    title = fields.CharField(max_length=120)
    created = fields.DateTimeField(auto_now_add=True)


class BoardMember(Model):
    class Meta:
        table = "tb_board_members"
        unique_together = ("board", "user")

    board = fields.ForeignKey(Board, on_delete="CASCADE")
    user = fields.ForeignKey(User, on_delete="CASCADE")
    joined = fields.DateTimeField(auto_now_add=True)


class Card(Model):
    class Meta:
        table = "tb_cards"
        ordering = ["position", "id"]

    board = fields.ForeignKey(Board, on_delete="CASCADE")
    title = fields.CharField(max_length=200)
    description = fields.TextField(default="")
    status = fields.CharField(max_length=10, default="todo")
    position = fields.IntegerField(default=0)
    assignee = fields.ForeignKey(User, on_delete="CASCADE", null=True)
    created = fields.DateTimeField(auto_now_add=True)


ALL_MODELS = (User, Board, BoardMember, Card)
