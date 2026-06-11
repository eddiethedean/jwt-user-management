from __future__ import annotations

from fastapi_workbench.path_safety import (
    public_base_includes_mount,
    safe_url_path,
    workbench_mount_redirect_url,
    workbench_relative_redirect_url,
)


def test_safe_url_path_strips_traversal() -> None:
    assert safe_url_path("/../admin") == "/"


def test_public_base_includes_mount_by_segments() -> None:
    assert public_base_includes_mount("https://x.com/prefix/app", "/prefix/app")
    assert not public_base_includes_mount("https://x.com/prefix", "/prefix/app")


def test_workbench_mount_redirect_uses_root_path() -> None:
    assert (
        workbench_mount_redirect_url("/s/abc/p/proj", "/admin") == "/s/abc/p/proj/admin"
    )
    assert workbench_mount_redirect_url("/s/abc/p/proj", "/") == "/s/abc/p/proj"


def test_workbench_relative_redirect_nested() -> None:
    assert (
        workbench_relative_redirect_url("/admin/users/5", "/login") == "../../../login"
    )
    assert workbench_relative_redirect_url("/", "/") == "."
