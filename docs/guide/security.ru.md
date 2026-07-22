# Безопасность

Безопасность — это набор **умолчаний**, а не чек-лист, прикручиваемый потом.

## ORM / SQL-инъекции

- **Значения всегда биндятся драйвером** — никогда не подставляются в SQL
  строками.
- **Идентификаторы** (таблицы/колонки/алиасы) валидируются (`^[A-Za-z_]\w*$`) и
  квотируются; всё прочее вызывает `UnsafeIdentifierError`.
- **Lookup'ы — строгий белый список**: неизвестный lookup вызывает исключение.
- **Wildcards `LIKE`** в пользовательском вводе экранируются через `ESCAPE`.
- **`LIMIT`/`OFFSET`** приводятся к целым числам.

Тестовый набор включает явные тесты на инъекции, доказывающие, что враждебный
ввод остаётся связанным параметром. См. [ORM](../orm/index.md).

## Маскирование логов

Логирующий middleware маскирует чувствительные ключи **до** записи — см.
[Логирование](logging.md). Пароли не попадают в поток логов, хотя middleware
видит сырой запрос.

## Шифрование файлов на диске

`FileField` шифрует загрузки AES-256-GCM; утёкшая папка хранилища невосстановима
без отдельного ключа, а подмена данных обнаруживается. См.
[Шифрованные файлы](../orm/files.md).

## Cookies и CSRF

- `set_signed_cookie` / `get_signed_cookie` используют HMAC-SHA256, так что
  cookies нельзя подделать.
- `csrf_middleware` реализует паттерн signed double-submit-cookie для небезопасных
  методов.
- Cookies по умолчанию `SameSite=Lax`; при необходимости ставьте `secure=True`,
  `httponly=True`.

## Сессии и аутентификация

Встроено, только stdlib. Сессия целиком едет в HMAC-подписанной куке (stateless,
без серверного хранилища); пароли хешируются **scrypt** (`hashlib.scrypt`) в
самоописывающем формате — параметры стойкости можно поднять позже.

```python
# Middleware/__init__.py
from endocore.middleware import session_middleware
middlewares = [session_middleware(secret=env("SECRET_KEY"), secure=True)]
```

```python
# Api/v1/Login/Post.py
from endocore import Response, login, verify_password
from Models.user import User

async def handler(request):
    body = await request.json()
    user = await User.objects.filter(email=body["email"]).afirst()
    # None тоже сжигает полную scrypt-деривацию: неизвестный email отвечает
    # так же долго, как неверный пароль — перечислить аккаунты по таймингу нельзя.
    if not verify_password(body["password"], user.password_hash if user else None):
        return Response.json({"error": "invalid credentials"}, status=401)
    login(request, user.pk)                  # кладёт pk в сессию
    return Response.json({"ok": True})
```

```python
# Api/v1/Me/Get.py — 401 анонимным запросам, через DI
from endocore import Depends, Response, require_user_id

async def handler(request, user_id = Depends(require_user_id)):
    return Response.json({"user_id": user_id})
```

- `hash_password(pw)` → сохраните строку; `verify_password(pw, stored)` —
  сравнение за константное время; `needs_rehash(stored)` подскажет, когда
  перехешировать после логина.
- `login(request, pk)` / `logout(request)` / `user_id(request)` (→ pk или `None`).
- `request.session` — обычный dict; кука перезаписывается только если сессию
  меняли, и удаляется при очистке. Держите её маленькой (лимит куки ~4 КБ).
- Подделанная/протухшая кука сессии даёт чистую анонимную сессию, а не 500.

## Усиливающие middleware

```python
from endocore.middleware import (
    security_headers_middleware, cors_middleware, rate_limit_middleware,
    proxy_headers_middleware, timeout_middleware, csrf_middleware,
)

middlewares = [
    security_headers_middleware(hsts=True),          # nosniff, DENY frames, HSTS
    cors_middleware(allow_origins=["https://app.example.com"]),
    rate_limit_middleware(limit=100, window=60),
    proxy_headers_middleware(trusted=["10.0.0.1"]),  # X-Forwarded-* только от этих
    timeout_middleware(seconds=30),
    csrf_middleware(secret="…"),
]
```

## Лимит размера тела

Приложение отклоняет тела запросов больше `max_body_size` (по умолчанию 16 МБ)
со статусом 413 — защита от загрузок, исчерпывающих память.

## Чек-лист для продакшена

- [ ] Задайте сильный секрет для подписанных cookies / CSRF (из env, не в коде).
- [ ] `configure_storage(key=…)` из секрет-менеджера; сделайте бэкап ключа.
- [ ] Включите `security_headers_middleware(hsts=True)` за TLS.
- [ ] Ограничьте `cors_middleware(allow_origins=[…])` своими фронтендами.
- [ ] Поставьте `proxy_headers_middleware(trusted=[…])`, если вы за балансировщиком.
- [ ] Добавьте `rate_limit_middleware` (или лимитер на Redis) на публичные маршруты.
- [ ] Работайте по HTTPS; терминируйте TLS на прокси.
