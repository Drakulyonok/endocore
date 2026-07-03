# Request & Response

EndoCore ships its own thin `Request`/`Response` over the raw ASGI scope — no
Starlette.

## Request

```python
async def handler(request):
    request.method                       # "POST"
    request.path                         # "/v1/user/42"
    request.path_params["id"]            # "42"

    request.query.get("page")            # first value or None
    request.query.getlist("tag")         # all values
    request.headers.get("content-type")  # lower-cased keys
    request.cookies.get("session")

    data = await request.json()          # parsed body (BadRequest on bad JSON)
    raw  = await request.body()          # bytes
    form = await request.form()          # urlencoded or multipart
    files = await request.files()        # {field: UploadFile}
```

### Query params

`request.query` is a multi-dict: `[]`/`.get()` return the first value,
`.getlist()` returns all.

### Forms & uploads

`await request.form()` parses both `application/x-www-form-urlencoded` and
`multipart/form-data`. Uploaded files are `UploadFile` objects:

```python
form = await request.form()
name = form.get("name")
upload = form.files["avatar"]            # UploadFile
content = upload.read()                  # bytes
upload.filename, upload.content_type, upload.size
```

### Cookies (incl. signed)

```python
request.cookies.get("session")
request.get_signed_cookie("session", secret="…", max_age=3600)   # verifies HMAC
```

### Streaming large bodies

```python
async for chunk in request.stream():     # don't mix with body()/json()
    process(chunk)
```

The app enforces a body-size limit (`max_body_size`, default 16 MB) — oversize
bodies raise `PayloadTooLarge` (413).

## Response

```python
from endocore import Response

Response.json({"ok": True}, status=201, headers={"X-Foo": "bar"})
Response.text("hello")
Response.redirect("/login", status=307)
Response.no_content()                    # 204
Response(b"...", media_type="image/png") # raw bytes
```

A handler can also just return a value and let the framework coerce it:

| Return | Becomes |
|--------|---------|
| `Response` | as-is |
| `dict` / `list` | JSON 200 |
| `str` | text 200 |
| `None` | 204 |
| `(content, status)` / `(content, status, headers)` | JSON with that status |

### Cookies

```python
resp = Response.json({"ok": True})
resp.set_cookie("session", "abc", httponly=True, samesite="lax", max_age=3600)
resp.set_signed_cookie("session", "abc", secret="…")   # HMAC-signed
resp.delete_cookie("session")
```

### Background tasks

Run work **after** the response is sent:

```python
async def send_email():
    ...

return Response.json({"queued": True}, background=send_email)
```

### Streaming responses

```python
from endocore import StreamingResponse

async def rows():
    for i in range(1000):
        yield f"row {i}\n"

return StreamingResponse(rows(), media_type="text/plain")
```
