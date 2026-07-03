"""ORM models for the example app + connection bootstrap.

Importing this module configures the default connection and ensures the tables
exist, so endpoints can just ``from Models.blog import Post`` and query.
"""

from endocore.orm import Model, configure, create_all, fields

# A local SQLite file next to the app. Swap for Postgres with:
#   configure(backend="postgres", host="localhost", dbname="app", user="...", password="...")
configure(backend="sqlite", database="endocore_example.db")


class Post(Model):
    title = fields.CharField(max_length=200)
    body = fields.TextField(default="")
    views = fields.IntegerField(default=0)


create_all(Post)
