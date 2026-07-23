# Кэш

Кэш запоминает результаты медленной работы — тяжёлого запроса, обращения к
внешнему API — и повторные запросы получают мгновенный ответ вместо повторения
той же работы.

В EndoCore это небольшой кэш с бэкендами **в памяти** и **Redis**, плюс
декоратор `@cached`.

## Настройка и использование

```python
from endocore import configure_cache, get_cache

configure_cache("memory")                       # локальный для процесса, с TTL
# или:  configure_cache("redis", client=redis_client)  # pip install "endocore[redis]"

cache = get_cache()
cache.set("user:1", {"name": "Ada"}, ttl=60)    # ttl в секундах (опционально)
cache.get("user:1", default=None)
cache.has("user:1")
cache.delete("user:1")
cache.incr("hits", amount=1)                     # почти атомарный счётчик
cache.clear()
```

Если `configure_cache` не вызывался, `get_cache()` возвращает дефолтный кэш в
памяти.

## Декоратор `@cached`

Мемоизация результата функции (sync или async) с опциональным TTL:

```python
from endocore import cached

@cached(ttl=30)
async def expensive(user_id: int):
    return await slow_lookup(user_id)

@cached(ttl=300, key=lambda a, b: f"sum:{a}:{b}")
def add(a, b):
    return a + b
```

## Инжект кэша

Через [DI](dependency-injection.md) — с помощью `CacheExtension` или провайдера:

```python
# extensions.py
from endocore.extensions import CacheExtension
extensions = [CacheExtension(backend="memory")]
```

```python
async def handler(request, cache):        # инжект по имени
    hit = cache.get("k")
    ...
```

## Redis-бэкенд

```python
# extensions.py
from endocore.extensions import RedisExtension, CacheExtension
extensions = [
    RedisExtension(url="redis://localhost:6379/0"),
    CacheExtension(backend="redis"),      # использует Redis-клиент выше
]
```

Значения сериализуются pickle; ключи получают префикс-неймспейс
(по умолчанию `endocore:`).

!!! warning "Подписывайте кэш, если Redis не полностью доверенный"
    `pickle.loads()` над тем, что вернул Redis, безопасен ровно настолько,
    насколько безопасен сам Redis — тот, кто может записать этот ключ
    (открытый наружу/неправильно настроенный инстанс, скомпрометированный
    соседний сервис), получает выполнение кода при следующем чтении из кэша.
    Передайте `secret=`, чтобы подписывать каждое значение HMAC при записи и
    проверять подпись при чтении; отсутствующая или неверная подпись
    трактуется как промах кэша, а не как исключение:

    ```python
    extensions = [
        RedisExtension(url="redis://localhost:6379/0"),
        CacheExtension(backend="redis", secret=env("SECRET_KEY")),
    ]
    ```

    Без `secret=` значения остаются неподписанными (как раньше), и один раз
    на экземпляр кэша выводится предупреждение.

!!! tip "Rate limiting"
    `rate_limit_middleware(..., redis_client=...)` делит один лимит на все
    воркеры вместо подсчёта на процесс — см. [Middleware](middleware.ru.md).
