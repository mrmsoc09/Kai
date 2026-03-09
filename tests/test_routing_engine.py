from ai_kernel.wrappers.gateway.routing_engine import route


def test_route_has_status():
    res = route(task="coding", privacy_tier=1)
    assert "status" in res
