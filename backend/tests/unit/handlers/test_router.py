"""Unit tests for src.handlers.router."""

from src.handlers.router import Router


def _noop(*args, **kwargs):
    return {}


class TestRouter:
    def test_public_route_match(self):
        router = Router()
        router.public("POST", "/api/auth/login", _noop)
        result = router.dispatch("POST", "/api/auth/login")
        assert result is not None
        handler, path_params, authenticated = result
        assert handler is _noop
        assert path_params == {}
        assert authenticated is False

    def test_protected_route_match(self):
        router = Router()
        router.protected("GET", "/api/analyses", _noop)
        result = router.dispatch("GET", "/api/analyses")
        assert result is not None
        handler, path_params, authenticated = result
        assert handler is _noop
        assert path_params == {}
        assert authenticated is True

    def test_path_param_extraction(self):
        router = Router()
        router.protected("GET", "/api/scan/{scan_id}", _noop)
        result = router.dispatch("GET", "/api/scan/abc-123")
        assert result is not None
        _, path_params, _ = result
        assert path_params == {"scan_id": "abc-123"}

    def test_no_match_returns_none(self):
        router = Router()
        router.public("POST", "/api/auth/login", _noop)
        result = router.dispatch("GET", "/api/nonexistent")
        assert result is None

    def test_method_mismatch_returns_none(self):
        router = Router()
        router.public("POST", "/api/auth/login", _noop)
        result = router.dispatch("GET", "/api/auth/login")
        assert result is None

    def test_dispatch_public_handler_called_with_event(self):
        calls = []

        def capturing_handler(event, **path_params):
            calls.append((event, path_params))
            return {"statusCode": 200}

        router = Router()
        router.public("POST", "/api/auth/login", capturing_handler)

        handler, path_params, authenticated = router.dispatch("POST", "/api/auth/login")
        event = {"httpMethod": "POST", "path": "/api/auth/login"}
        result = handler(event, **path_params)

        assert result == {"statusCode": 200}
        assert calls == [(event, {})]
        assert not authenticated

    def test_dispatch_protected_handler_called_with_event_and_path_params(self):
        calls = []

        def capturing_handler(event, auth, scan_id):
            calls.append((event, auth, scan_id))
            return {"statusCode": 200}

        router = Router()
        router.protected("GET", "/api/scan/{scan_id}", capturing_handler)

        handler, path_params, authenticated = router.dispatch("GET", "/api/scan/abc-123")
        event = {"httpMethod": "GET"}
        auth = object()
        result = handler(event, auth, **path_params)

        assert result == {"statusCode": 200}
        assert calls == [(event, auth, "abc-123")]
        assert authenticated

    def test_multi_segment_path_param(self):
        router = Router()
        router.protected("POST", "/api/scan/{scan_id}/confirm", _noop)
        result = router.dispatch("POST", "/api/scan/xyz-789/confirm")
        assert result is not None
        _, path_params, authenticated = result
        assert path_params == {"scan_id": "xyz-789"}
        assert authenticated is True
