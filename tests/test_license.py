import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_the_repository_is_all_rights_reserved_and_says_so_in_three_places() -> None:
    licence = (ROOT / "LICENSE").read_text(encoding="utf-8")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "All rights reserved" in licence and "NOT open source" in licence
    assert "Copy, reproduce, modify" in licence and "train a machine-learning model" in licence
    assert project["license"] == {"file": "LICENSE"}
    assert project["classifiers"] == ["License :: Other/Proprietary License"]
    assert "All rights reserved" in readme and "(LICENSE)" in readme
    # a real name is not in a public file: the holder is the account that owns the repository
    assert "Copyright (c) 2026 conlusive" in licence


def test_both_images_copy_the_licence_file_the_project_metadata_names() -> None:
    # without it the build of the package fails: "license file not found"
    for name in ("Dockerfile.dashboard", "Dockerfile.pipeline"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "COPY pyproject.toml uv.lock README.md LICENSE ./" in text, name
