# Errors & exceptions

Need to answer "404 Not Found" or "401 Unauthorized" from deep inside your
code? Raise an exception — EndoCore catches it anywhere in a handler or
middleware and turns it into a JSON response with the right status code.

```python
from endocore import Request, Response, NotFound, Unauthorized

async def handler(request: Request) -> Response:
    user = find_user(request.path_params["id"])
    if user is None:
        raise NotFound("user not found")     # -> 404 {"error": "user not found"}
    if not user.active:
        raise Unauthorized()                 # -> 401 {"error": "Unauthorized"}
    return Response.json(user.to_dict())
```

## Built-in exceptions

Import from `endocore`:

| Class | Status |
|-------|--------|
| `BadRequest` | 400 |
| `Unauthorized` | 401 |
| `Forbidden` (= `PermissionDenied`) | 403 |
| `NotFound` | 404 |
| `MethodNotAllowed` | 405 |
| `Conflict` | 409 |
| `PayloadTooLarge` | 413 |
| `UnprocessableEntity` | 422 |
| `TooManyRequests` | 429 |
| `HTTPError(status, detail)` | any |

Each takes an optional detail message; without one it uses a sensible default
(`NotFound()` → "Not Found").

```python
from endocore import HTTPError
raise HTTPError(418, "I'm a teapot")
```

## How errors are handled

The always-on logging middleware:

- catches any `HTTPError` (from a handler **or** any middleware) and returns
  `{"error": detail}` with the right status;
- catches any other exception, logs the traceback (with the masked payload and
  request id), and returns a **500**;
- so **one broken handler never kills the connection silently**.

The response body for an HTTP exception is `{"error": <detail>}`. For a pydantic
validation failure (422) `detail` is a list of `{"field", "message"}` entries.

## Boot-time errors

An endpoint file that fails to **import** doesn't crash the app — it's collected
and reported in the boot summary and by `endo check`. The rest of the app keeps
serving.
