"""Tests for the X-Ray tracing utility module."""

from unittest.mock import MagicMock, patch

import pytest


class TestConfigureTracing:
    """Tests for setup_tracing()."""

    def test_noop_when_daemon_address_not_set(self, monkeypatch):
        """setup_tracing() does nothing when AWS_XRAY_DAEMON_ADDRESS is absent."""
        monkeypatch.delenv("AWS_XRAY_DAEMON_ADDRESS", raising=False)

        mock_patch = MagicMock()
        with patch.dict("sys.modules", {"aws_xray_sdk": MagicMock(), "aws_xray_sdk.core": MagicMock(patch=mock_patch)}):
            from src.utilities.tracing import setup_tracing
            setup_tracing()

        mock_patch.assert_not_called()

    def test_patches_boto3_and_httpx_when_daemon_available(self, monkeypatch):
        """setup_tracing() calls patch(["boto3", "httpx"]) when daemon is available."""
        monkeypatch.setenv("AWS_XRAY_DAEMON_ADDRESS", "127.0.0.1:2000")

        mock_patch_fn = MagicMock()
        mock_core = MagicMock()
        mock_core.patch = mock_patch_fn

        with patch.dict("sys.modules", {"aws_xray_sdk": MagicMock(), "aws_xray_sdk.core": mock_core}):
            # Force re-import to pick up the mocked module
            import importlib
            import src.utilities.tracing
            importlib.reload(src.utilities.tracing)
            src.utilities.tracing.setup_tracing()

        mock_patch_fn.assert_called_once_with(["boto3", "httpx"])

    def test_import_error_propagates(self, monkeypatch):
        """ImportError propagates if aws-xray-sdk is missing (fail-fast)."""
        monkeypatch.setenv("AWS_XRAY_DAEMON_ADDRESS", "127.0.0.1:2000")

        # Remove cached module to force re-import
        import sys as sys_module
        for key in list(sys_module.modules.keys()):
            if "aws_xray_sdk" in key:
                del sys_module.modules[key]

        with patch.dict("sys.modules", {"aws_xray_sdk": None, "aws_xray_sdk.core": None}):
            import importlib
            import src.utilities.tracing
            importlib.reload(src.utilities.tracing)
            with pytest.raises((ImportError, ModuleNotFoundError)):
                src.utilities.tracing.setup_tracing()
