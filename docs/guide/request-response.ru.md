# Request и Response

Каждый обработчик получает `Request` — всё, что прислал клиент (URL, заголовки,
query-параметры, тело), — и возвращает `Response` — всё, что вы отправляете в
ответ. Эта страница — полный справочник по обоим.

Оба класса — собственные тонкие обёртки EndoCore над сырым ASGI, без Starlette
под капотом.

## Request

```python
async def handler(request):
    request.method                       # "POST"
    request.path                         # "/v1/user/42"
    request.path_params["id"]            # "42"

    request.query.get("page")            # первое значение или None
    request.query.getlist("tag")         # все значения
    request.headers.get("content-type")  # ключи в нижнем регистре
    request.cookies.get("session")

    data = await request.json()          # распарсенное тело (BadRequest при плохом JSON)
    raw  = await request.body()          # bytes
    form = await request.form()          # urlencoded или multipart
    files = await request.files()        # {field: UploadFile}
```

### Query-параметры

`request.query` — мульти-словарь: `[]`/`.get()` возвращают первое значение,
`.getlist()` — все.

### Формы и загрузки файлов

`await request.form()` парсит и `application/x-www-form-urlencoded`, и
`multipart/form-data`. Загруженные файлы — объекты `UploadFile`:

```python
form = await request.form()
name = form.get("name")
upload = form.files["avatar"]            # UploadFile
content = upload.read()                  # bytes
upload.filename, upload.content_type, upload.size
```

### Cookies (включая подписанные)

```python
request.cookies.get("session")
request.get_signed_cookie("session", secret="…", max_age=3600)   # проверяет HMAC
```

### Стриминг больших тел

```python
async for chunk in request.stream():     # не смешивайте с body()/json()
    process(chunk)
```

Приложение ограничивает размер тела (`max_body_size`, по умолчанию 16 МБ) —
слишком большие тела вызывают `PayloadTooLarge` (413).

!!! warning "`request.stream()` на практике редко стримит из сети"
    Всегда включённый логирующий middleware (самый внешний слой на каждом
    запросе, его нельзя убрать для отдельного маршрута) вызывает
    `request.json()` **до** того, как вообще запустится ваш обработчик —
    для *каждого* запроса, независимо от метода или content-type — чисто
    чтобы залогировать замаскированный payload, даже если обработчик потом
    упадёт. Этот вызов сначала полностью вычитывает тело в память
    (ограничено `max_body_size`), и только *потом* пытается распарсить его
    как JSON, молча отбрасывая результат, если не получилось. К моменту,
    когда сработает `request.stream()` в вашем обработчике, тело уже
    забуферено — `stream()` просто отдаёт эти байты одним чанком (см. его
    докстринг: «если тело уже забуферено, отдаёт его один раз»).
    `request.stream()` — реальный и корректно реализованный механизм для
    случая, когда до него ещё никто не трогал тело (например, вызов
    `Request` напрямую вне полного конвейера middleware, как это делают
    собственные тесты фреймворка), но внутри обычного работающего
    приложения ожидайте, что всё тело запроса уже находится в памяти
    (вплоть до `max_body_size`) до того, как до него доберётся любой код
    уровня обработчика — стриминговый или нет.

## Response

```python
from endocore import Response

Response.json({"ok": True}, status=201, headers={"X-Foo": "bar"})
Response.text("hello")
Response.redirect("/login", status=307)
Response.no_content()                    # 204
Response(b"...", media_type="image/png") # сырые байты
```

Обработчик может просто вернуть значение — фреймворк приведёт его сам:

| Возврат | Становится |
|--------|---------|
| `Response` | как есть |
| `dict` / `list` | JSON 200 |
| `str` | текст 200 |
| `None` | 204 |
| `(content, status)` / `(content, status, headers)` | JSON с этим статусом |

### Cookies

```python
resp = Response.json({"ok": True})
resp.set_cookie("session", "abc", httponly=True, samesite="lax", max_age=3600)
resp.set_signed_cookie("session", "abc", secret="…")   # подписан HMAC
resp.delete_cookie("session")
```

### Фоновые задачи

Выполнить работу **после** отправки ответа:

```python
async def send_email():
    ...

return Response.json({"queued": True}, background=send_email)
```

### Стриминговые ответы

```python
from endocore import StreamingResponse

async def rows():
    for i in range(1000):
        yield f"row {i}\n"

return StreamingResponse(rows(), media_type="text/plain")
```
