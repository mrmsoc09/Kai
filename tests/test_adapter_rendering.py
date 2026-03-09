from pathlib import Path


def test_templates_exist():
    assert Path("ai-kernel/templates/memory/GEMINI.template.md").exists()
    assert Path("ai-kernel/templates/adapter/gemini.settings.template.json").exists()
