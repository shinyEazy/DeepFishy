from deepfishy.infra.config.model_registry import (
    get_default_llm_name,
    load_model_registry,
)


def test_load_model_registry_returns_dictionary() -> None:
    config = load_model_registry()
    assert isinstance(config, dict)
    assert "deepfishy" in config


def test_get_default_llm_name_returns_config_value() -> None:
    value = get_default_llm_name()
    assert isinstance(value, str)
    assert value
