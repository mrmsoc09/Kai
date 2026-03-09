from pathlib import Path


def test_runtime_memory_paths_exist():
    for path in [
        Path("runtime/memory/shared"),
        Path("runtime/memory/sessions"),
        Path("runtime/memory/artifacts"),
        Path("runtime/memory/indexes"),
    ]:
        assert path.exists()
