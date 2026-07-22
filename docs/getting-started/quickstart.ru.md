# Быстрый старт

Рабочий API примерно за минуту. Без конфигов и регистрации маршрутов — вы
создаёте папки и файлы, EndoCore их отдаёт. На этой странице разобрано ровно
то, что происходит на каждом шаге и почему, включая пару моментов, на
которых обычно спотыкаются в первый раз (они явно обозначены ниже, а не
оставлены на самостоятельное открытие).

## 1. Сгенерируйте проект

```bash
pip install "endocore[watch]"    # [watch] включает автоперезагрузку dev-сервера — см. шаг 2
end new blog
cd blog
```

!!! note "PowerShell"
    В PowerShell пишите `endo` вместо `end` (`endo new blog`) — `end` там
    зарезервированное слово (ключевое слово блока PowerShell). Тот же CLI,
    другое имя; все остальные команды ниже работают одинаково что с `end`,
    что с `endo`.

`end new blog` пишет ровно это и ничего больше (это код
`endocore/cli/commands/new.py`, а не приблизительное описание):

```text
blog/
  Api/
    v1/
      Health/
        Get.py          # GET /v1/health — проверка живости, чтобы `end dev`
                         # сразу было что отдавать
  Middleware/
    __init__.py         # пустой список `middlewares = [...]`, закомментированные примеры
  Services/  Models/  Utils/  Tests/    # пустые, кроме .gitkeep в каждой
  hooks.py              # списки `on_startup` / `on_shutdown`, оба пустые заглушки
  README.md
```

Файла `extensions.py` пока **нет** — он опционален и нужен только когда вы
реально подключаете интеграцию сервиса (Redis, Celery, email); см.
[Расширения](../extensions/index.md). Не создавайте его заранее «на всякий
случай».

## 2. Запустите dev-сервер

```bash
end dev
```

В консоли появится примерно такое:

```text
[INFO] EndoCore booted: loaded 1 route, 0 middleware, 0 files with errors
[INFO] dev watcher on: .../blog/Api
[INFO] Uvicorn running on http://127.0.0.1:8000
```

Откройте `http://127.0.0.1:8000/v1/health` — получите `{"status": "ok"}`.
А на `http://127.0.0.1:8000/docs` — интерактивный **Swagger UI**, где каждый
endpoint можно подёргать прямо из браузера. (`/docs` здесь включён
автоматически, потому что `end dev` запускает приложение с `dev=True` — в
продакшене он по умолчанию выключен; см. [Конфигурация](../guide/configuration.md).)

!!! warning "Нет строки `dev watcher on: ...`? Перезагрузка не сработает"
    Внутрипроцессный вотчер файлов нуждается в опциональном пакете
    `watchfiles` — как раз для этого в шаге 1 стоял `pip install
    "endocore[watch]"`. Без него `end dev` всё равно запускает приложение
    совершенно нормально, просто логирует `dev watcher disabled (install
    'watchfiles' for auto-reload)` вместо строки про вотчер, и каждое
    сохранение в шагах 3–6 ниже потребует ручного перезапуска (`Ctrl+C`,
    снова `end dev`), чтобы изменения применились. Если пропустили
    экстру `[watch]`, поставьте её сейчас: `pip install watchfiles`.

## 3. Добавьте endpoint

Сгенерируйте:

```bash
end create user/profile get
# -> Api/v1/User/Profile/Get.py   (GET /v1/user/profile)
```

`end create` сам переводит каждый сегмент пути в PascalCase (`user` →
`User`) и пишет минимальное тело обработчика; целится он в **последнюю
существующую версию**, если вы её не указали (здесь — `v1`, поскольку это
единственная версия). Запустите её ещё раз с теми же аргументами — она не
затрёт ваши правки, а напечатает `exists: ...` и оставит файл как есть.

…или создайте файл сами — `end create` это удобство, а не обязательное
требование. **Папка — это путь, имя файла — это метод**, и точка:

```python
# Api/v1/User/Profile/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    return Response.json({"name": "Ada", "role": "admin"})
```

Сохраните файл — при запущенном вотчере EndoCore пересканирует `Api/` и
переимпортирует изменённый обработчик прямо в процессе (без рестарта
сервера, без разрыва соединений). Откройте
`http://127.0.0.1:8000/v1/user/profile` — endpoint уже работает. Полный
набор правил, включая несколько граничных случаев, которые стоит знать до
того, как ваше дерево разрастётся до сотни файлов, — в
[Роутинге](../guide/routing.md).

## 4. Динамические сегменты

Папка с именем `[id]` захватывает параметр пути, дословно (в отличие от
обычных папок, регистр **не** приводится к нижнему — см.
[Роутинг](../guide/routing.md#dynamic-segments)):

```python
# Api/v1/User/[id]/Get.py
from endocore import Request, Response

async def handler(request: Request) -> Response:
    user_id = request.path_params["id"]         # "42" для /v1/user/42 — всегда str
    return Response.json({"id": user_id})
```

`request.path_params["id"]` — всегда `str`: EndoCore никогда не угадывает,
что `"42"` нужно превратить в `int` `42`. Приводите тип сами
(`int(request.path_params["id"])`), если обработчику нужно число;
невалидное приведение — забота вашего кода (например, оберните его в
`raise HTTPError(422, "id must be numeric")`), а не роутера.

## 5. Чтение входных данных

```python
# Api/v1/User/Post.py   (POST /v1/user)
from endocore import Request, Response, HTTPError

async def handler(request: Request) -> Response:
    data = await request.json()
    if not data.get("name"):
        raise HTTPError(422, "name is required")
    return Response.json({"created": data["name"]}, status=201)
```

`await request.json()` возвращает `None` для пустого тела (это не ошибка) и
поднимает `BadRequest` (→ 400) для тела, которое не является валидным JSON —
так что `data.get("name")` выше поднимет `AttributeError` на `None`, если
клиент вообще не прислал тело; защититесь от этого явно (`data = await
request.json() or {}`), если только пустое тело действительно не должно
быть 500-й. `request` также даёт `request.query` (распарсенная строка
запроса), `request.headers`, `request.cookies` и `await request.form()` /
`await request.files()` для multipart-загрузок — см.
[Request и Response](../guide/request-response.md).

## 6. Подключите ORM

```python
# Models/blog.py
from endocore.orm import Model, fields, configure, create_all

configure(backend="sqlite", database="blog.db")

class Post(Model):
    title = fields.CharField(max_length=200)
    body  = fields.TextField(default="")

create_all(Post)
```

```python
# Api/v1/Post/Post.py   (POST /v1/post)
from endocore import Request, Response
from Models.blog import Post

async def handler(request: Request) -> Response:
    data = await request.json()
    post = Post.objects.create(title=data["title"], body=data.get("body", ""))
    return Response.json({"id": post.pk, "title": post.title}, status=201)
```

Здесь важно понять две вещи, а не просто скопировать:

- **`configure()` и `create_all()` выполняются один раз, при первом импорте
  `Models.blog`** — Python кеширует модули в `sys.modules`, так что сколько
  бы разных файлов обработчиков ни делали `from Models.blog import Post`,
  тело модуля (а значит и `configure`/`create_all`) выполнится ровно один
  раз, в момент *первого* импорта (на практике — при старте, поскольку
  EndoCore жадно импортирует каждый найденный обработчик). Именно поэтому
  пример работает без какой-либо явной обвязки «запуск приложения».
- **Вызывайте `configure()` для соединения `"default"` строго в одном
  месте** — если два разных файла моделей оба вызовут `configure(backend=
  "sqlite", database=...)` для одного алиаса, тот, который Python
  импортирует *вторым*, молча заменит первое соединение (`configure()`
  всегда перезаписывает; см. [Транзакции](../orm/transactions.md)).
  Держите один файл (этот, `Models/blog.py`, или отдельный `Models/db.py` в
  проекте побольше) единственным местом, где вызывается `configure()`, а
  остальные файлы моделей пусть просто импортируют `fields, Model`,
  полагаясь на то, что этот вызов уже отработал.

`blog.db` создаётся **относительно текущей рабочей директории процесса**
(там, откуда вы запустили `end dev`), а не относительно файла модели —
стоит знать заранее, а не удивляться потом, откуда взялся файл в
неожиданном месте. Полное руководство по ORM — поля, лукапы, связи,
async-API — в [руководстве по ORM](../orm/index.md).

## 7. Осмотрите приложение

```bash
end routes         # все маршруты + файл, в который они мапятся
end check          # битые хендлеры, дубли маршрутов, пропущенные файлы (с причинами)
end openapi        # печать OpenAPI-схемы
```

`end check` стоит запускать всякий раз, когда что-то *должно* быть
маршрутом, но не появляется: он печатает ровно причину, по которой сканер
пропустил каждый такой файл (не та папка версии, не то расположение), а не
оставляет вас гадать.

Это весь цикл. Дальше — [Туториал](tutorial.md): соберём полноценный
версионированный API с сервисами, middleware и миграциями.
