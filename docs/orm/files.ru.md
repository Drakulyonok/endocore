# Шифрованные файлы

`FileField` хранит загруженные файлы **зашифрованными на диске** с помощью
AES-256-GCM. Если папка хранилища утечёт, файлы нельзя прочитать или
восстановить без отдельного ключа шифрования — а любая подмена обнаруживается.

Требуется экстра `files`:

```bash
pip install "endocore[files]"
```

## Настройка хранилища и ключа

```python
from endocore.orm import configure_storage, generate_key

# сгенерируйте ОДИН ключ и храните его отдельно (env / секрет-менеджер) — не рядом с файлами
key = generate_key()        # 32-байтная url-safe base64 строка

configure_storage(root="/var/data/uploads", key=key)
# или через env: ENDOCORE_FILE_KEY=... ; configure_storage(root="/var/data/uploads")
```

`root` может быть **любой папкой**. Файлы пишутся в неё со случайными именами и
расширением `.enc`.

## Объявление поля

```python
from endocore.orm import Model, fields

class Document(Model):
    title = fields.CharField(max_length=200)
    file  = fields.FileField(upload_to="docs")     # подпапка внутри корня хранилища
```

## Использование

```python
doc = Document.objects.create(title="Report", file=b"...raw bytes...")
# или файлоподобный объект:
with open("report.pdf", "rb") as fh:
    doc = Document.objects.create(title="Report", file=fh)

doc.file.name          # ключ, хранящийся в БД (например "docs/ab12...enc")
doc.file.read()        # расшифровка по требованию -> bytes
doc.file.size()        # размер на диске
doc.file.open()        # BytesIO расшифрованного содержимого
doc.file.delete()      # удалить файл
```

**Колонка в базе хранит только непрозрачный ключ** — никогда не содержимое и не
угадываемый путь.

## Свойства безопасности

- **AES-256-GCM** (аутентифицированное шифрование) через проверенную библиотеку
  `cryptography` — никакой самодельной криптографии.
- **Свежий случайный nonce на каждый файл**; сохранённый путь привязывается как
  additional authenticated data, поэтому файл нельзя незаметно подменить или
  переименовать.
- **Случайные имена файлов** ничего не говорят о содержимом.
- **Fail-closed**: использование `FileField` без настроенного ключа вызывает
  исключение — ничто никогда не запишется открытым текстом случайно.
- **Защита от path traversal**: `upload_to` и сохранённые ключи не могут выйти
  за пределы корня.

!!! danger "Управление ключом — на вас"
    Потеря ключа означает потерю файлов. Храните его в секрет-менеджере или
    переменной окружения, сделайте резервную копию и никогда не коммитьте в
    репозиторий.
