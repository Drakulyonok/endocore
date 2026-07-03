# Encrypted files

`FileField` stores uploaded files **encrypted at rest** with AES-256-GCM. If the
storage directory leaks, the files cannot be read or restored without the
separate encryption key — and any tampering is detected.

Requires the `files` extra:

```bash
pip install "endocore[files]"
```

## Configure storage + a key

```python
from endocore.orm import configure_storage, generate_key

# generate ONE key and keep it safe (env var / secret manager) — not with the files
key = generate_key()        # 32-byte url-safe base64 string

configure_storage(root="/var/data/uploads", key=key)
# or via env: ENDOCORE_FILE_KEY=... ; configure_storage(root="/var/data/uploads")
```

`root` can be **any folder**. Files are written under it with random names and a
`.enc` extension.

## Declare the field

```python
from endocore.orm import Model, fields

class Document(Model):
    title = fields.CharField(max_length=200)
    file  = fields.FileField(upload_to="docs")     # subfolder under the storage root
```

## Use it

```python
doc = Document.objects.create(title="Report", file=b"...raw bytes...")
# or a file-like object:
with open("report.pdf", "rb") as fh:
    doc = Document.objects.create(title="Report", file=fh)

doc.file.name          # the stored key held in the DB (e.g. "docs/ab12...enc")
doc.file.read()        # decrypts on demand -> bytes
doc.file.size()        # size on disk
doc.file.open()        # a BytesIO of the decrypted content
doc.file.delete()      # remove the file
```

The **database column only holds an opaque key** — never the content, never a
guessable path.

## Security properties

- **AES-256-GCM** (authenticated encryption) via the vetted `cryptography`
  library — no home-grown crypto.
- **Fresh random nonce per file**; the stored path is bound in as additional
  authenticated data, so a file can't be swapped/renamed undetected.
- **Random filenames** leak nothing about the content.
- **Fail-closed**: using a `FileField` without a configured key raises — nothing
  is ever written in plaintext by accident.
- **Path-traversal safe**: `upload_to` and stored keys can't escape the root.

!!! danger "Key management is on you"
    Losing the key means losing the files. Store it in a secret manager or an
    environment variable, back it up, and never commit it to the repo.
