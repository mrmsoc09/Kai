from __future__ import annotations

from apps.backend.src.core.hook_registry import HookRegistry


def test_hook_registry_runs_hooks_in_deterministic_order():
    registry = HookRegistry()
    seen: list[str] = []

    def cb_a(context):
        seen.append("a")
        return {"v": (context.get("v") or "") + "a"}

    def cb_b(context):
        seen.append("b")
        return {"v": (context.get("v") or "") + "b"}

    registry.register("pre_run", "b", cb_b, order=20)
    registry.register("pre_run", "a", cb_a, order=10)
    out = registry.run("pre_run", {"hook_type": "pre_run", "v": ""})
    assert seen == ["a", "b"]
    assert out["v"] == "ab"


def test_hook_registry_replaces_existing_name():
    registry = HookRegistry()

    def first(context):
        return {"x": "first"}

    def second(context):
        return {"x": "second"}

    registry.register("post_run", "same", first, order=10)
    registry.register("post_run", "same", second, order=10)
    out = registry.run("post_run", {"hook_type": "post_run"})
    assert out["x"] == "second"
