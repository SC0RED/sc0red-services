"""Tests for Company domain models."""

from src.models.model_company import (
    Company,
    CompanyProfile,
    Opportunity,
    OpportunityResult,
    RelatedService,
    RiskAssessment,
    RiskScore,
    Vendor,
)


class TestCompanyProfile:
    def test_create_minimal(self):
        profile = CompanyProfile(company_name="Acme", industry="SaaS")
        assert profile.company_name == "Acme"
        assert profile.industry == "SaaS"
        assert profile.products_services == []

    def test_create_full(self):
        profile = CompanyProfile(
            company_name="Acme Corp",
            industry="B2B SaaS - HR Technology",
            industry_sector="Technology",
            business_model="SaaS",
            description="HR tech platform",
            products_services=["ATS", "Payroll"],
            target_market="Mid-market companies",
            company_size="Mid-market 200-1000",
            revenue_model="subscription",
            tech_signals=["React", "AWS"],
            competitive_positioning="AI-first",
            ai_maturity="Partial adoption",
            key_risks_visible=["competitor growth"],
        )
        assert len(profile.products_services) == 2
        assert profile.industry_sector == "Technology"

    def test_required_fields(self):
        # company_name and industry are required (str, no default)
        profile = CompanyProfile(company_name="Test", industry="Tech")
        assert profile.company_name == "Test"


class TestRiskScore:
    def test_create(self):
        score = RiskScore(
            category="competitive_displacement",
            score=7,
            explanation="High risk",
            evidence="competitor raised Series C",
        )
        assert score.category == "competitive_displacement"
        assert score.score == 7
        assert score.evidence == "competitor raised Series C"

    def test_score_constraints(self):
        # Score must be >= 1 and <= 10
        score = RiskScore(category="data_ip", score=5)
        assert score.score == 5


class TestRiskAssessment:
    def test_create(self):
        assessment = RiskAssessment(
            risk_scores=[
                RiskScore(category="competitive_displacement", score=7),
                RiskScore(category="technology_obsolescence", score=5),
            ],
            overall_score=6.0,
            tier="high",
            top_risks=["competitive_displacement"],
            analysis_summary="Company faces moderate risk",
        )
        assert len(assessment.risk_scores) == 2
        assert assessment.overall_score == 6.0
        assert assessment.tier == "high"

    def test_defaults(self):
        assessment = RiskAssessment()
        assert assessment.overall_score == 0.0
        assert assessment.tier == "low"
        assert assessment.risk_scores == []


class TestOpportunity:
    def test_create_with_vendors(self):
        vendor = Vendor(name="DataRobot", url="https://datarobot.com", specialty="AutoML")
        service = RelatedService(service_type="ML Platform", vendors=[vendor])
        opportunity = Opportunity(
            title="Deploy AI Churn Prediction",
            risk_mitigated="customer_behavior",
            impact_rating="High",
            strategic_category="Revenue Capture",
            description="Implement churn prediction model",
            implementation_steps=["Step 1", "Step 2"],
            timeline="Medium-term (3-9 months)",
            investment_range="$100K-$500K",
            roi_estimate="20% reduction in churn",
            related_services=[service],
        )
        assert opportunity.title == "Deploy AI Churn Prediction"
        assert len(opportunity.related_services) == 1
        assert opportunity.related_services[0].vendors[0].name == "DataRobot"


class TestOpportunityResult:
    def test_create(self):
        result = OpportunityResult(
            opportunities=[
                Opportunity(title="Opp 1"),
                Opportunity(title="Opp 2"),
            ],
            top_three_immediate_actions=["Action 1", "Action 2", "Action 3"],
        )
        assert len(result.opportunities) == 2
        assert len(result.top_three_immediate_actions) == 3


class TestCompany:
    def test_create_minimal(self):
        company = Company(url="https://example.com")
        assert company.url == "https://example.com"
        assert company.id == ""
        assert company.profile is None
        assert company.risk_assessment is None

    def test_create_full(self):
        company = Company(
            id="abc-123",
            scan_id="scan-456",
            org_id="org-789",
            company_name="Acme",
            url="https://acme.com",
            actual_url="https://www.acme.com",
            profile=CompanyProfile(company_name="Acme", industry="SaaS"),
            risk_assessment=RiskAssessment(overall_score=5.0, tier="moderate"),
        )
        assert company.id == "abc-123"
        assert company.profile.company_name == "Acme"
        assert company.risk_assessment.tier == "moderate"

    def test_transient_fields_excluded(self):
        company = Company(url="https://example.com")
        company.scraped_text = "some content"
        company.scraped_links = [{"url": "https://a.com"}]
        company.scraped_title = "Title"

        dumped = company.model_dump()
        assert "scraped_text" not in dumped
        assert "scraped_links" not in dumped
        assert "scraped_title" not in dumped
