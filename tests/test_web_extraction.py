import httpx
import pytest

from app.services.web_extraction import _raise_for_bad_status, extract_text_from_html, validate_public_url


def test_extract_text_from_html_removes_scripts_and_keeps_title():
    title, text = extract_text_from_html(
        """
        <html>
          <head>
            <title>Refund Docs</title>
            <script>window.secret = "ignore me"</script>
          </head>
          <body>
            <main>
              <h1>Refund policy</h1>
              <p>Refund requests need an invoice number.</p>
            </main>
          </body>
        </html>
        """
    )

    assert title == "Refund Docs"
    assert "Refund policy" in text
    assert "invoice number" in text
    assert "ignore me" not in text


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://10.0.0.1/internal",
        "ftp://example.com/file",
    ],
)
def test_validate_public_url_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_public_url(url)


def test_403_status_becomes_user_friendly_error():
    response = httpx.Response(status_code=403, request=httpx.Request("GET", "https://example.com"))

    with pytest.raises(ValueError, match="403 Forbidden"):
        _raise_for_bad_status(response)
