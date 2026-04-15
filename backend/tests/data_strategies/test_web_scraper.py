"""Tests for web scraper context extraction."""

from bs4 import BeautifulSoup

from src.data_strategies.web_scraper_strategy import _extract_context_name


def _make_anchor(html):
    """Parse HTML and return the first <a> tag."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("a")


class TestExtractContextName:
    def test_heading_in_parent_article(self):
        html = """
        <article>
            <h3>Acme Corp</h3>
            <p>Description</p>
            <a href="https://acme.com">LEARN MORE</a>
        </article>
        """
        assert _extract_context_name(_make_anchor(html)) == "Acme Corp"

    def test_heading_in_parent_div(self):
        html = """
        <div>
            <h2>Beta Inc</h2>
            <a href="https://beta.com">Visit Website</a>
        </div>
        """
        assert _extract_context_name(_make_anchor(html)) == "Beta Inc"

    def test_img_alt_in_parent_article(self):
        html = """
        <article>
            <img alt="stripe logo" src="stripe.png">
            <a href="https://stripe.com">LEARN MORE</a>
        </article>
        """
        assert _extract_context_name(_make_anchor(html)) == "Stripe Logo"

    def test_aria_label_on_link(self):
        html = '<a href="https://acme.com" aria-label="Visit Acme Corp">→</a>'
        assert _extract_context_name(_make_anchor(html)) == "Visit Acme Corp"

    def test_title_attribute_on_link(self):
        html = '<a href="https://acme.com" title="Acme Corp Website">click</a>'
        assert _extract_context_name(_make_anchor(html)) == "Acme Corp Website"

    def test_no_context_returns_empty(self):
        html = '<div><a href="https://acme.com">LEARN MORE</a></div>'
        assert _extract_context_name(_make_anchor(html)) == ""

    def test_heading_preferred_over_img_alt(self):
        html = """
        <article>
            <h3>Real Name</h3>
            <img alt="logo image" src="logo.png">
            <a href="https://acme.com">LEARN MORE</a>
        </article>
        """
        assert _extract_context_name(_make_anchor(html)) == "Real Name"

    def test_stops_at_article_boundary(self):
        html = """
        <section>
            <h2>Portfolio Section</h2>
            <article>
                <a href="https://acme.com">LEARN MORE</a>
            </article>
        </section>
        """
        # Should not find heading from outer section
        assert _extract_context_name(_make_anchor(html)) == ""

    def test_ignores_learn_in_aria_label(self):
        html = '<a href="https://acme.com" aria-label="Learn more about us">Go</a>'
        assert _extract_context_name(_make_anchor(html)) == ""

    def test_short_text_ignored(self):
        html = '<a href="https://x.com" title="AB">Go</a>'
        assert _extract_context_name(_make_anchor(html)) == ""
