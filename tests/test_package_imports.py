from importlib import import_module


def test_deepfishy_package_imports() -> None:
    modules = [
        "deepfishy",
        "deepfishy.app",
        "deepfishy.features",
        "deepfishy.infra",
        "deepfishy.shared",
    ]

    for module_name in modules:
        module = import_module(module_name)
        assert module is not None


def test_logging_module_imports() -> None:
    assert import_module("deepfishy.shared.logging") is not None
