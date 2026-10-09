from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.ingestion import PageScraper

FULL_PAGE_HTML = """
<html>
<head><title>Installation - Tailwind CSS</title></head>
<body>
  <header><nav>Navigation links here</nav></header>
  <main>
    <h1>Installation</h1>
    <p>Install Tailwind CSS via npm to get started with the framework.</p>
    <p>Run the following command to install:</p>
    <pre><code>npm install tailwindcss</code></pre>
  </main>
  <aside>Related articles</aside>
  <footer>Copyright notice and links</footer>
</body>
</html>
"""

MINIMAL_HTML = """
<html><body><p>Short.</p></body></html>
"""


@pytest.fixture
def scraper() -> PageScraper:
    return PageScraper()


def test_parse_extracts_h1_as_title(scraper: PageScraper) -> None:
    page = scraper._parse('https://example.com/docs', FULL_PAGE_HTML)
    assert page is not None
    assert page.title == 'Installation'


def test_parse_excludes_nav_and_footer(scraper: PageScraper) -> None:
    page = scraper._parse('https://example.com/docs', FULL_PAGE_HTML)
    assert page is not None
    assert 'Navigation links here' not in page.content
    assert 'Copyright notice' not in page.content
    assert 'Related articles' not in page.content


def test_parse_includes_main_content(scraper: PageScraper) -> None:
    page = scraper._parse('https://example.com/docs', FULL_PAGE_HTML)
    assert page is not None
    assert 'Install Tailwind CSS' in page.content
    assert 'npm install' in page.content


def test_parse_returns_none_for_very_short_content(scraper: PageScraper) -> None:
    page = scraper._parse('https://example.com', MINIMAL_HTML)
    assert page is None


def test_extract_links_returns_same_domain_links(scraper: PageScraper) -> None:
    html = """
    <html><body>
      <a href="/docs/installation">Installation</a>
      <a href="/docs/configuration">Configuration</a>
      <a href="https://external.com/other">External</a>
      <a href="https://tailwindcss.com/docs/utilities">Utilities</a>
    </body></html>
    """
    links = scraper.extract_links('https://tailwindcss.com/docs', html)

    assert 'https://tailwindcss.com/docs/installation' in links
    assert 'https://tailwindcss.com/docs/configuration' in links
    assert 'https://tailwindcss.com/docs/utilities' in links
    assert not any('external.com' in link for link in links)


def test_extract_links_filters_to_base_path(scraper: PageScraper) -> None:
    html = """
    <html><body>
      <a href="/docs/page">Doc page</a>
      <a href="/blog/post">Blog post (different section)</a>
      <a href="/">Home</a>
    </body></html>
    """
    links = scraper.extract_links('https://example.com/docs', html)

    assert 'https://example.com/docs/page' in links
    assert not any('/blog/' in link for link in links)
    assert not any(link == 'https://example.com/' for link in links)


def test_extract_links_removes_fragments(scraper: PageScraper) -> None:
    html = '<html><body><a href="/docs/page#section">Link</a></body></html>'
    links = scraper.extract_links('https://example.com/docs', html)
    assert all('#' not in link for link in links)


def test_extract_links_deduplicates(scraper: PageScraper) -> None:
    html = """
    <html><body>
      <a href="/docs/page">Link 1</a>
      <a href="/docs/page">Link 1 again</a>
    </body></html>
    """
    links = scraper.extract_links('https://example.com/docs', html)
    assert len(links) == len(set(links))


# ── scrape_page ───────────────────────────────────────────────────────────────

async def test_scrape_page_success(scraper: PageScraper) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = FULL_PAGE_HTML

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    page = await scraper.scrape_page('https://example.com/docs', mock_client)
    assert page is not None
    assert page.title == 'Installation'


async def test_scrape_page_http_error_returns_none(scraper: PageScraper) -> None:
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError('connection timeout'))

    page = await scraper.scrape_page('https://example.com/docs', mock_client)
    assert page is None


# ── _parse edge branches ──────────────────────────────────────────────────────

def test_parse_uses_title_tag_when_no_h1(scraper: PageScraper) -> None:
    html = """
    <html><head><title>Page From Title Tag</title></head>
    <body><main>
      <p>This is a sufficiently long paragraph of documentation content that passes the one hundred character minimum threshold for content extraction.</p>
    </main></body></html>
    """
    page = scraper._parse('https://example.com', html)
    assert page is not None
    assert page.title == 'Page From Title Tag'


def test_parse_returns_none_when_no_body(scraper: PageScraper) -> None:
    html = '<html></html>'
    page = scraper._parse('https://example.com', html)
    assert page is None
