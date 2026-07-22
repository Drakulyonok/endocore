# Versioning

Versioning lets you change what an endpoint returns without breaking apps that
already use it: old clients keep calling `/v1`, new ones get `/v2`.

In EndoCore this is not a subsystem — it's a special case of routing. The first
path segment matching `^v\d+$` is the version, and it's just a folder.

## The model

- A version applies to the **whole endpoint with all its methods**.
- `v1` and `v2` **coexist** — old clients keep working.
- After you create `v2`, `v1` behaves **identically** to before. If a change in
  `v2` could touch `v1`, the versioning would be fake.

```text
Api/
  v1/User/Role/Post.py     # POST /v1/user/role   (old contract)
  v2/User/Role/Post.py     # POST /v2/user/role   (new contract)
```

## Creating a version

```bash
end version create 2          # copy the latest version -> v2
end version create 2 --from 1 # branch from a specific version
end version create 2 --empty  # scaffolds without bodies
end version list              # v1, v2
```

`end version create` is `shutil.copytree` with a filter: it copies **endpoints**
and **local services**, and repoints version-qualified imports so `v2` uses its
own services — never `v1`'s.

## Local vs global services

```text
Api/v1/User/Services/create_role.py    # LOCAL  — versioned, copied into v2
Services/auth_service.py               # GLOBAL — shared across all versions
```

- **Local services** (`Api/vN/.../Services/`) are versioned and copied, so a v2
  change can't affect v1.
- **Global services** (`/Services/` at the app root) are shared by every version
  and never copied.

This split is exactly what keeps versioning honest: v2's edits touch only v2's
local code and endpoints.

## Creating endpoints in a version

```bash
end create user/role post          # into the latest version
end create v2/user/role post       # into an explicit version
```

Without a `vN` prefix, `end create` targets the latest existing version (or `v1`
if none exist).
