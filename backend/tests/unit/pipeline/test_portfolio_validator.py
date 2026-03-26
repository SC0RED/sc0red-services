"""Tests for portfolio_validator module."""

from unittest.mock import MagicMock

from src.pipeline.portfolio_validator import validate_portfolio_companies


def _make_company(name: str, url: str) -> dict[str, str]:
    return {"name": name, "url": url}


def _build_mock_factory(responses: dict[str, bool]) -> MagicMock:
    """Build a mock AIClientFactory whose client returns structured responses.

    ``responses`` maps company_name -> is_portfolio_company boolean.
    """
    factory = MagicMock()

    def get_client(**_kwargs: object) -> MagicMock:
        client = MagicMock()

        def query_structured(input_text: str, json_schema: object) -> MagicMock:
            for name, is_valid in responses.items():
                if name in input_text:
                    response = MagicMock()
                    response.content = {"is_portfolio_company": is_valid}
                    response.metadata = {}
                    return response
            # Default: keep the company
            response = MagicMock()
            response.content = {"is_portfolio_company": True}
            response.metadata = {}
            return response

        client.query_structured = query_structured
        return client

    factory.get_client = get_client
    return factory


class TestValidatePortfolioCompanies:
    def test_filters_non_portfolio_companies(self) -> None:
        companies = [
            _make_company("Acme Corp", "https://acme.com"),
            _make_company("About Us", "https://firm.com/about"),
            _make_company("Beta Inc", "https://beta.com"),
        ]
        mock_factory = _build_mock_factory(
            {
                "Acme Corp": True,
                "About Us": False,
                "Beta Inc": True,
            }
        )

        result = validate_portfolio_companies(
            companies=companies,
            firm_url="https://firm.com",
            ai_client_factory=mock_factory,
        )

        names = [c["name"] for c in result]
        assert "Acme Corp" in names
        assert "Beta Inc" in names
        assert "About Us" not in names

    def test_keeps_all_when_all_valid(self) -> None:
        companies = [
            _make_company("Acme Corp", "https://acme.com"),
            _make_company("Beta Inc", "https://beta.com"),
        ]
        mock_factory = _build_mock_factory(
            {
                "Acme Corp": True,
                "Beta Inc": True,
            }
        )

        result = validate_portfolio_companies(
            companies=companies,
            firm_url="https://firm.com",
            ai_client_factory=mock_factory,
        )

        assert len(result) == 2

    def test_empty_list_returns_empty(self) -> None:
        mock_factory = MagicMock()
        result = validate_portfolio_companies(
            companies=[],
            firm_url="https://firm.com",
            ai_client_factory=mock_factory,
        )
        assert result == []

    def test_keeps_company_on_ai_error(self) -> None:
        companies = [
            _make_company("Acme Corp", "https://acme.com"),
            _make_company("Error Co", "https://error.com"),
        ]

        factory = MagicMock()
        call_count = 0

        def get_client(**_kwargs: object) -> MagicMock:
            client = MagicMock()

            def query_structured(input_text: str, json_schema: object) -> MagicMock:
                nonlocal call_count
                call_count += 1
                if "Error Co" in input_text:
                    raise RuntimeError("AI service unavailable")
                response = MagicMock()
                response.content = {"is_portfolio_company": True}
                response.metadata = {}
                return response

            client.query_structured = query_structured
            return client

        factory.get_client = get_client

        result = validate_portfolio_companies(
            companies=companies,
            firm_url="https://firm.com",
            ai_client_factory=factory,
        )

        # Both should be kept — error companies are not filtered out
        assert len(result) == 2

    def test_string_content_is_parsed(self) -> None:
        """Test that string JSON content from the AI is correctly parsed."""
        companies = [_make_company("Acme Corp", "https://acme.com")]

        factory = MagicMock()

        def get_client(**_kwargs: object) -> MagicMock:
            client = MagicMock()

            def query_structured(input_text: str, json_schema: object) -> MagicMock:
                response = MagicMock()
                response.content = '{"is_portfolio_company": false}'
                response.metadata = {}
                return response

            client.query_structured = query_structured
            return client

        factory.get_client = get_client

        result = validate_portfolio_companies(
            companies=companies,
            firm_url="https://firm.com",
            ai_client_factory=factory,
        )

        assert len(result) == 0
