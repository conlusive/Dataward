import jobmarket


def test_package_exposes_version() -> None:
    assert jobmarket.__version__ == "0.1.0"
