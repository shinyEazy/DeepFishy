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
