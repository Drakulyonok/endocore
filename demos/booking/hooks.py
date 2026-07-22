from endocore.orm import create_all

from Models.core import ALL_MODELS


def init_db() -> None:
    create_all(*ALL_MODELS)


on_startup = [init_db]
on_shutdown = []
