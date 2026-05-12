# Per-source scraper modules (Plan A Task 6+). Each module exposes
# `parse_section_html(html, url) -> list[Chunk]` and `fetch_and_chunk()`
# (async generator) that streams chunks through the per-host breaker.
