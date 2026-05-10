from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode
from xml.etree import ElementTree

import httpx

from ainewsagent.domain.models import Item, Source

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
ARXIV_API_URL = "https://export.arxiv.org/api/query"


def build_query(categories: list[str]) -> str:
    return " OR ".join(f"cat:{category}" for category in categories)


def parse_arxiv_feed(xml_text: str) -> list[Item]:
    root = ElementTree.fromstring(xml_text)
    items: list[Item] = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = _text(entry, f"{ATOM}id")
        title = " ".join(_text(entry, f"{ATOM}title").split())
        summary = " ".join(_text(entry, f"{ATOM}summary").split())
        published = _parse_datetime(_text(entry, f"{ATOM}published"))
        authors = [
            _text(author, f"{ATOM}name")
            for author in entry.findall(f"{ATOM}author")
            if _text(author, f"{ATOM}name")
        ]
        categories = [
            category.attrib["term"]
            for category in entry.findall(f"{ATOM}category")
            if category.attrib.get("term")
        ]
        pdf_url = ""
        for link in entry.findall(f"{ATOM}link"):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
                break
        comment = _text(entry, f"{ARXIV}comment")
        text = summary if not comment else f"{summary}\nComment: {comment}"
        if raw_id and title:
            items.append(
                Item(
                    id=raw_id.rsplit("/", 1)[-1],
                    source=Source.ARXIV,
                    title=title,
                    url=raw_id,
                    text=text,
                    published_at=published,
                    authors=authors,
                    categories=categories,
                    metrics={"has_pdf": 1 if pdf_url else 0},
                )
            )
    return items


def fetch_recent_papers(categories: list[str], max_results: int) -> list[Item]:
    params = {
        "search_query": build_query(categories),
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API_URL}?{urlencode(params)}"
    with httpx.Client(timeout=30.0, headers={"User-Agent": "ainewsagent/0.1"}) as client:
        response = client.get(url)
        response.raise_for_status()
    return parse_arxiv_feed(response.text)


def _text(node: ElementTree.Element, path: str) -> str:
    child = node.find(path)
    return child.text.strip() if child is not None and child.text else ""


def _parse_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
