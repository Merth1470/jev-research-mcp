"""Shared fixtures: realistic documentation HTML and search results."""

from __future__ import annotations

import pytest

DOC_HTML = """<!DOCTYPE html><html><head><title>Async Fetch Guide</title>
<style>.x{color:red}</style></head>
<body>
<nav><a href=\"/\">Home</a><a href=\"/pricing\">Pricing</a></nav>
<script>var track = 1;</script>
<noscript>enable js</noscript>
<div class=\"cookie-banner\">We use cookies <button>Accept</button></div>
<h1>Enable streaming</h1>
<p>Set this option to true.</p>
<p>Streaming reduces memory usage for large responses.</p>
<h2>Code example</h2>
<pre><code class=\"language-python\">import asyncio

async def fetch(url):
    async with semaphore:
        return await client.get(url)
</code></pre>
<h2>Options</h2>
<ul><li>timeout in seconds</li><li>max retries</li></ul>
<blockquote>Always revalidate redirect targets.</blockquote>
<table><tr><th>Option</th><th>Default</th></tr>
<tr><td>timeout</td><td>15</td></tr></table>
<div class=\"social-share\">Share on X</div>
<footer>Copyright 2026 Example Corp. All rights reserved.</footer>
</body></html>"""


@pytest.fixture
def doc_html() -> str:
    return DOC_HTML


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TYPESAFE_API_KEY",
        "JEV_API_KEY",
        "BRAVE_API_KEY",
        "SEARCH_API_KEY",
        "SEARCH_PROVIDER",
        "MAX_SEARCH_RESULTS",
        "MAX_SOURCES",
        "MAX_EVIDENCE_TOKENS",
        "LOG_LEVEL",
        "ENABLE_UI",
        "UI_HOST",
        "UI_PORT",
        "UI_OPEN_BROWSER",
    ):
        monkeypatch.delenv(name, raising=False)
