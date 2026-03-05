"""Tests for CompanyAccessor facade."""

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    OpportunityResult,
    RiskAssessment,
    RiskScore,
)


class TestCompanyAccessorRead:
    def test_get_entity_id(self):
        company = Company(id="abc-123", url="https://example.com")
        accessor = CompanyAccessor(company)
        assert accessor.get_entity_id() == "abc-123"

    def test_get_entity_name_from_profile(self):
        company = Company(
            url="https://example.com",
            profile=CompanyProfile(company_name="Acme Corp", industry="SaaS"),
        )
        accessor = CompanyAccessor(company)
        assert accessor.get_entity_name() == "Acme Corp"

    def test_get_entity_name_from_company_name(self):
        company = Company(url="https://example.com", company_name="Fallback Name")
        accessor = CompanyAccessor(company)
        assert accessor.get_entity_name() == "Fallback Name"

    def test_get_entity_name_empty(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        assert accessor.get_entity_name() == ""

    def test_get_region_returns_industry_sector(self):
        company = Company(
            url="https://example.com",
            profile=CompanyProfile(
                company_name="Test",
                industry="SaaS",
                industry_sector="Technology",
            ),
        )
        accessor = CompanyAccessor(company)
        assert accessor.get_region() == "Technology"

    def test_get_region_empty_without_profile(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        assert accessor.get_region() == ""

    def test_get_probability_with_risk(self):
        company = Company(
            url="https://example.com",
            risk_assessment=RiskAssessment(overall_score=7.0),
        )
        accessor = CompanyAccessor(company)
        assert accessor.get_probability() == 0.7

    def test_get_probability_without_risk(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        assert accessor.get_probability() == 0.0

    def test_get_total_score(self):
        company = Company(
            url="https://example.com",
            risk_assessment=RiskAssessment(overall_score=8.5),
        )
        accessor = CompanyAccessor(company)
        assert accessor.get_total_score() == 8.5

    def test_get_categories(self):
        company = Company(
            url="https://example.com",
            risk_assessment=RiskAssessment(
                risk_scores=[
                    RiskScore(category="competitive_displacement", score=7),
                    RiskScore(category="data_ip", score=3),
                ]
            ),
        )
        accessor = CompanyAccessor(company)
        categories = accessor.get_categories()
        assert len(categories) == 2
        assert categories[0]["category"] == "competitive_displacement"

    def test_get_dealbreaker_triggered(self):
        company = Company(
            url="https://example.com",
            risk_assessment=RiskAssessment(tier="critical"),
        )
        accessor = CompanyAccessor(company)
        assert accessor.get_dealbreaker_triggered() is True

    def test_get_dealbreaker_not_triggered(self):
        company = Company(
            url="https://example.com",
            risk_assessment=RiskAssessment(tier="moderate"),
        )
        accessor = CompanyAccessor(company)
        assert accessor.get_dealbreaker_triggered() is False


class TestCompanyAccessorSetters:
    def test_set_profile(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        profile = CompanyProfile(company_name="New Name", industry="Fintech")
        accessor.set_profile(profile)
        assert accessor.company.profile.company_name == "New Name"

    def test_set_risk_assessment(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        assessment = RiskAssessment(overall_score=6.0, tier="high")
        accessor.set_risk_assessment(assessment)
        assert accessor.company.risk_assessment.tier == "high"

    def test_set_opportunities(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        result = OpportunityResult(
            opportunities=[],
            top_three_immediate_actions=["Action 1"],
        )
        accessor.set_opportunities(result)
        assert len(accessor.company.opportunity_result.top_three_immediate_actions) == 1

    def test_set_url(self):
        company = Company(url="https://old.com")
        accessor = CompanyAccessor(company)
        accessor.set_url("https://new.com")
        assert accessor.company.url == "https://new.com"

    def test_set_actual_url(self):
        company = Company(url="https://firm.com")
        accessor = CompanyAccessor(company)
        accessor.set_actual_url("https://company.com")
        assert accessor.company.actual_url == "https://company.com"

    def test_set_and_get_scraped_text(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        accessor.set_scraped_text("Hello world content")
        assert accessor.get_scraped_text() == "Hello world content"

    def test_set_and_get_scraped_links(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        links = [{"url": "https://a.com", "text": "Link A"}]
        accessor.set_scraped_links(links)
        assert accessor.get_scraped_links() == links

    def test_set_error(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        accessor.set_error("Something went wrong")
        assert accessor.company.error == "Something went wrong"

    def test_set_id(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)
        accessor.set_id("new-id")
        assert accessor.company.id == "new-id"


class TestCompanyAccessorNullBranches:
    """Test fallback branches when risk_assessment is None."""

    def test_get_total_score_without_risk(self):
        accessor = CompanyAccessor(Company(url="https://example.com"))
        assert accessor.get_total_score() == 0.0

    def test_get_categories_without_risk(self):
        accessor = CompanyAccessor(Company(url="https://example.com"))
        assert accessor.get_categories() == []

    def test_get_dealbreaker_without_risk(self):
        accessor = CompanyAccessor(Company(url="https://example.com"))
        assert accessor.get_dealbreaker_triggered() is False

    def test_set_scan_id(self):
        accessor = CompanyAccessor(Company(url="https://example.com"))
        accessor.set_scan_id("scan-123")
        assert accessor.company.scan_id == "scan-123"

    def test_set_org_id(self):
        accessor = CompanyAccessor(Company(url="https://example.com"))
        accessor.set_org_id("org-123")
        assert accessor.company.org_id == "org-123"

    def test_set_and_get_scraped_title(self):
        accessor = CompanyAccessor(Company(url="https://example.com"))
        accessor.set_scraped_title("Page Title")
        assert accessor.get_scraped_title() == "Page Title"


class TestCompanyAccessorDefault:
    def test_default_constructor(self):
        accessor = CompanyAccessor()
        assert accessor.company is not None
        assert accessor.company.url == ""
