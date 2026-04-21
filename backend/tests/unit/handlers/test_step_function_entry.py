"""Tests for Step Function Lambda entry points."""

from unittest.mock import patch


class TestEntryPoints:
    @patch("src.handlers.step_function_entry.handle_send_wave")
    def test_send_wave_entry(self, mock_handler):
        mock_handler.return_value = {"remaining_count": 0}

        from src.handlers.step_function_entry import handle_send_wave_event

        result = handle_send_wave_event({"companies": []}, None)

        mock_handler.assert_called_once_with({"companies": []}, None)
        assert result == {"remaining_count": 0}

    @patch("src.handlers.step_function_entry.handle_check_wave")
    def test_check_wave_entry(self, mock_handler):
        mock_handler.return_value = {"wave_done": True}

        from src.handlers.step_function_entry import handle_check_wave_event

        result = handle_check_wave_event({"wave_company_ids": []}, None)

        mock_handler.assert_called_once()
        assert result == {"wave_done": True}

    @patch("src.handlers.step_function_entry.handle_mark_complete")
    def test_mark_complete_entry(self, mock_handler):
        mock_handler.return_value = {"status": "complete"}

        from src.handlers.step_function_entry import handle_mark_complete_event

        result = handle_mark_complete_event({"scan_id": "s-1"}, None)

        mock_handler.assert_called_once()
        assert result == {"status": "complete"}
