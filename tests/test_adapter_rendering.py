from pathlib import Path


def test_templates_exist():
    assert Path("ai_kernel/templates/memory/GEMINI.template.md").exists()
    assert Path("ai_kernel/templates/adapter/gemini.settings.template.json").exists()
