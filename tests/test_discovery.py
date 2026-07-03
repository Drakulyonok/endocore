"""Tree scanning: which files become routes and which are skipped."""

from __future__ import annotations

from endocore.core.discovery import Segment, scan_routes, list_versions


def _write(path, text="x = 1\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_segment_parse():
    assert Segment.parse("User") == Segment("User", "user", False)
    assert Segment.parse("[id]") == Segment("[id]", "id", True)


def test_scan_classifies_files(tmp_path):
    api = tmp_path / "Api"
    _write(api / "v1" / "User" / "Role" / "Post.py")
    _write(api / "v1" / "User" / "[id]" / "Get.py")
    _write(api / "v1" / "User" / "Services" / "create_role.py")  # local service, not a route
    _write(api / "v1" / "helper.py")                             # non-method file, ignored
    _write(api / "notaversion" / "User" / "Get.py")             # outside vN, skipped

    specs, skipped = scan_routes(api)

    urls = sorted(s.url for s in specs)
    assert urls == ["/v1/user/role", "/v1/user/{id}"]
    methods = {s.method for s in specs}
    assert methods == {"POST", "GET"}
    # The service file inside Services/ and the non-version tree are recorded as skipped.
    reasons = {sf.file.name for sf in skipped}
    assert "create_role.py" in reasons or all("Services" not in str(s.file) for s in specs)


def test_list_versions_sorted_numerically(tmp_path):
    api = tmp_path / "Api"
    for v in ("v1", "v2", "v10"):
        (api / v).mkdir(parents=True)
    assert list_versions(api) == ["v1", "v2", "v10"]


def test_scan_missing_api_dir(tmp_path):
    specs, skipped = scan_routes(tmp_path / "does_not_exist")
    assert specs == [] and skipped == []
