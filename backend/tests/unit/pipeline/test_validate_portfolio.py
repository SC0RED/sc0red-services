"""Tests for ValidatePortfolioCompanies pipeline step."""

from unittest.mock import MagicMock

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.validate_portfolio import ValidatePortfolioCompanies


def _make_company(name: str, url: str) -> dict[str, str]:
    return {"name": name, "url": url}


def _build_mock_factory(responses: dict[str, bool]) -> MagicMock:
    """Build a mock AIClientFactory whose client returns structured responses.

    ``responses`` maps company_name -> is_portfolio_company boolean.
    """
    factory = MagicMock()

    def get_client(**_kwargs: object) -> MagicMock:
        client = MagicMock()

        def query_structured(*, input_text: str, json_schema: object) -> MagicMock:
            for name, is_valid in responses.items():
                if name in input_text:
                    response = MagicMock()
                    response.content = {"is_portfolio_company": is_valid}
                    response.metadata = {}
                    return response
            response = MagicMock()
            response.content = {"is_portfolio_company": True}
            response.metadata = {}
            return response

        client.query_structured = query_structured
        return client

    factory.get_client = get_client
    return factory


def _build_step_with_companies(
    companies: list[dict[str, str]],
    ai_client_factory: MagicMock | None = None,
    auto_included: list[dict[str, str]] | None = None,
) -> ValidatePortfolioCompanies:
    """Create a wired ValidatePortfolioCompanies step with mock executor and accessor."""
    step = ValidatePortfolioCompanies(ai_client_factory=ai_client_factory)

    company = Company(url="https://firm.com")
    accessor = CompanyAccessor(company)
    step._entity_accessor = accessor

    executor = MagicMock()
    executor.details = {
        "portfolio_companies": companies,
        "portfolio_auto_included": auto_included or [],
    }
    step._request_executor = executor

    return step


class TestValidatePortfolioCompanies:
    def test_filters_non_portfolio_companies(self) -> None:
        companies = [
            _make_company("Acme Corp", "https://acme.com"),
            _make_company("About Us", "https://firm.com/about"),
            _make_company("Beta Inc", "https://beta.com"),
        ]
        mock_factory = _build_mock_factory(
            {"Acme Corp": True, "About Us": False, "Beta Inc": True}
        )
        step = _build_step_with_companies(companies, mock_factory)

        step.execute()

        details_call = step._request_executor.add_details.call_args[0][0]
        validated = details_call["portfolio_companies"]
        names = [c["name"] for c in validated]
        assert "Acme Corp" in names
        assert "Beta Inc" in names
        assert "About Us" not in names
        assert details_call["portfolio_count"] == 2
        assert details_call["portfolio_validated_from"] == 3

    def test_keeps_all_when_all_valid(self) -> None:
        companies = [
            _make_company("Acme Corp", "https://acme.com"),
            _make_company("Beta Inc", "https://beta.com"),
        ]
        mock_factory = _build_mock_factory({"Acme Corp": True, "Beta Inc": True})
        step = _build_step_with_companies(companies, mock_factory)

        step.execute()

        details_call = step._request_executor.add_details.call_args[0][0]
        validated = details_call["portfolio_companies"]
        assert len(validated) == 2

    def test_fail_open_on_ai_error(self) -> None:
        companies = [
            _make_company("Acme Corp", "https://acme.com"),
            _make_company("Error Co", "https://error.com"),
        ]

        factory = MagicMock()

        def get_client(**_kwargs: object) -> MagicMock:
            client = MagicMock()

            def query_structured(*, input_text: str, json_schema: object) -> MagicMock:
                if "Error Co" in input_text:
                    raise RuntimeError("AI service unavailable")
                response = MagicMock()
                response.content = {"is_portfolio_company": True}
                response.metadata = {}
                return response

            client.query_structured = query_structured
            return client

        factory.get_client = get_client

        step = _build_step_with_companies(companies, factory)
        step.execute()

        details_call = step._request_executor.add_details.call_args[0][0]
        validated = details_call["portfolio_companies"]
        assert len(validated) == 2

    def test_empty_candidates_returns_auto_included(self) -> None:
        """With no candidates, final list is the auto-included set."""
        mock_factory = MagicMock()
        auto = [_make_company("Confirmed Co", "https://confirmed.com")]
        step = _build_step_with_companies([], mock_factory, auto_included=auto)

        step.execute()

        step._request_executor.mark_question_complete.assert_called_once_with(
            "validate_portfolio"
        )
        details_call = step._request_executor.add_details.call_args[0][0]
        assert details_call["portfolio_companies"] == auto
        assert details_call["portfolio_count"] == 1
        assert details_call["portfolio_validated_from"] == 0

    def test_empty_candidates_and_no_auto_included_is_empty(self) -> None:
        mock_factory = MagicMock()
        step = _build_step_with_companies([], mock_factory)

        step.execute()

        step._request_executor.mark_question_complete.assert_called_once_with(
            "validate_portfolio"
        )
        details_call = step._request_executor.add_details.call_args[0][0]
        assert details_call["portfolio_companies"] == []
        assert details_call["portfolio_count"] == 0

    def test_without_ai_client_factory_keeps_all(self) -> None:
        """Without AI factory, fail-open: keep candidates alongside auto-included."""
        companies = [_make_company("Acme Corp", "https://acme.com")]
        auto = [_make_company("Confirmed Co", "https://confirmed.com")]
        step = _build_step_with_companies(
            companies, ai_client_factory=None, auto_included=auto
        )

        step.execute()

        step._request_executor.mark_question_complete.assert_called_once_with(
            "validate_portfolio"
        )
        details_call = step._request_executor.add_details.call_args[0][0]
        assert len(details_call["portfolio_companies"]) == 2
        assert details_call["portfolio_count"] == 2
        assert details_call["portfolio_validated_from"] == 1

    def test_auto_included_preserved_alongside_validated(self) -> None:
        """Auto-included companies are merged with validated candidates."""
        candidates = [
            _make_company("Acme Corp", "https://acme.com"),
            _make_company("About Us", "https://firm.com/about"),
        ]
        auto = [_make_company("Confirmed Co", "https://confirmed.com")]
        mock_factory = _build_mock_factory({"Acme Corp": True, "About Us": False})
        step = _build_step_with_companies(candidates, mock_factory, auto_included=auto)

        step.execute()

        details_call = step._request_executor.add_details.call_args[0][0]
        names = [c["name"] for c in details_call["portfolio_companies"]]
        assert "Confirmed Co" in names  # auto-included, skipped validation
        assert "Acme Corp" in names  # validated
        assert "About Us" not in names  # filtered out
        assert details_call["portfolio_count"] == 2
        assert details_call["portfolio_validated_from"] == 2
