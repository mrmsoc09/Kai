import pytest
from fastapi.testclient import TestClient
from kai_master import app, KaiEngine
from unittest.mock import MagicMock, patch

# Initialize TestClient for the FastAPI app
client = TestClient(app)

# Mock KaiEngine instance to prevent actual scan execution during tests
def mock_kai_engine():
    mock_engine = MagicMock(spec=KaiEngine)
    mock_engine.target = "test.com"
    mock_engine.run_id = "test_run"
    mock_engine.base_output = MagicMock()
    mock_engine.project_root = MagicMock()
    mock_engine._init_directories = MagicMock()
    mock_engine.workflow_recon_surface_map = MagicMock() # Mock the workflow method
    return mock_engine

@pytest.fixture(autouse=True)
def mock_kai_engine_global():
    global kai_engine_instance
    with patch('kai_master.KaiEngine', new=mock_kai_engine) as mock_constructor:
        yield mock_constructor # This yields the mock constructor
        # Reset the global instance after each test
        kai_engine_instance = None

def test_start_scan_api_success():
    response = client.post(
        "/admin/start_scan",
        json={
            "target_domain": "test.com",
        }
    )

    assert response.status_code == 200
    assert "Scan initiated" in response.json()["message"]
    
    # Verify that KaiEngine was instantiated (or its mock was called)
    mock_kai_engine_global.return_value.assert_called_once_with(target_domain="test.com")
    # Verify that the workflow was triggered
    mock_kai_engine_global.return_value.return_value.workflow_recon_surface_map.assert_called_once()

def test_start_scan_api_missing_domain():
    response = client.post(
        "/admin/start_scan",
        json={}
    )

    assert response.status_code == 422 # Unprocessable Entity for Pydantic validation error
    assert "validation error" in response.json()["detail"][0]["msg"]
