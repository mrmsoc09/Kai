from ai_kernel.wrappers.gateway.capability_registry import load_capabilities, find_models


def test_load_capabilities():
    caps = load_capabilities()
    assert isinstance(caps, dict)


def test_find_models_returns_list():
    models = find_models("coding", min_privacy=1)
    assert isinstance(models, list)
