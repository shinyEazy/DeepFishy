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


def test_report_application_modules_import() -> None:
    assert (
        import_module("deepfishy.features.reports.application.generate_report")
        is not None
    )
    assert (
        import_module(
            "deepfishy.features.reports.application.generate_dataset_reports"
        )
        is not None
    )


def test_infra_llm_modules_import() -> None:
    assert import_module("deepfishy.infra.llm.chat_factory") is not None
    assert import_module("deepfishy.infra.llm.embedding_factory") is not None


def test_core_infra_adapters_import() -> None:
    assert import_module("deepfishy.infra.storage.minio") is not None
    assert import_module("deepfishy.infra.vector.milvus") is not None
    assert import_module("deepfishy.infra.graph.neo4j") is not None
