from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ainewsagent.domain.models import Item, Source

X_HOME = "https://x.com/home"


class XReadError(RuntimeError):
    pass


def login_x(profile_dir: Path, browser_channel: str = "") -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = _launch_context(
            p,
            profile_dir=profile_dir,
            headless=False,
            viewport={"width": 1280, "height": 900},
            browser_channel=browser_channel,
        )
        page = browser.new_page()
        page.goto(X_HOME, wait_until="domcontentloaded")
        print("X login window is open. Log in, then press Enter here to close it.")
        input()
        browser.close()


def read_x_sources(
    profile_dir: Path,
    *,
    list_url: str = "",
    accounts: list[str] | None = None,
    max_posts: int = 40,
    browser_channel: str = "",
) -> list[Item]:
    accounts = accounts or []
    targets: list[str] = []
    if list_url:
        targets.append(list_url)
    targets.extend(f"https://x.com/{account.lstrip('@')}" for account in accounts)
    if not targets:
        return []

    profile_dir.mkdir(parents=True, exist_ok=True)
    collected: list[Item] = []
    with sync_playwright() as p:
        browser = _launch_context(
            p,
            profile_dir=profile_dir,
            headless=True,
            viewport={"width": 1280, "height": 1400},
            browser_channel=browser_channel,
        )
        page = browser.new_page()
        try:
            for target in targets:
                collected.extend(_read_target(page, target, max_posts=max_posts))
        finally:
            browser.close()
    return _dedupe_items(collected)[:max_posts]


def check_x_browser(profile_dir: Path | str, browser_channel: str = "") -> None:
    with sync_playwright() as p:
        browser = _launch_context(
            p,
            profile_dir=Path(profile_dir),
            headless=True,
            viewport={"width": 640, "height": 480},
            browser_channel=browser_channel,
        )
        browser.close()


def _launch_context(p, *, profile_dir: Path, headless: bool, viewport: dict[str, int], browser_channel: str):
    kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": headless,
        "viewport": viewport,
    }
    if browser_channel:
        kwargs["channel"] = browser_channel
    try:
        return p.chromium.launch_persistent_context(**kwargs)
    except PlaywrightError as exc:
        message = str(exc)
        if "Executable doesn't exist" in message or "looks like Playwright was just installed" in message:
            raise XReadError(
                "Playwright Chromium is not installed. Run "
                "`python -m playwright install chromium`, or set `x_browser_channel: chrome` "
                "if Google Chrome is installed."
            ) from exc
        raise


def _read_target(page, target: str, *, max_posts: int) -> list[Item]:
    page.goto(target, wait_until="domcontentloaded", timeout=45_000)
    try:
        page.wait_for_selector("article", timeout=15_000)
    except PlaywrightTimeoutError as exc:
        if "login" in page.url.lower() or "flow/login" in page.url.lower():
            raise XReadError("X login is required. Run `ainewsagent login-x` first.") from exc
        raise XReadError(f"Could not load X posts from {target}") from exc

    for _ in range(4):
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(900)

    articles = page.locator("article").all()
    items: list[Item] = []
    for article in articles[: max_posts * 2]:
        item = parse_tweet_article(article, target)
        if item is not None:
            items.append(item)
        if len(items) >= max_posts:
            break
    return items


def parse_tweet_article(article, fallback_url: str) -> Item | None:
    text = " ".join(article.inner_text(timeout=3_000).split())
    if not text:
        return None

    link = _first_tweet_link(article) or fallback_url
    author = _extract_author(text)
    title = text[:120]
    published = _extract_time(article)
    metrics = _extract_metrics(text)
    return Item(
        id=link,
        source=Source.X,
        title=title,
        url=link,
        text=text,
        published_at=published,
        authors=[author] if author else [],
        metrics=metrics,
    )


def _first_tweet_link(article) -> str:
    links = article.locator('a[href*="/status/"]').evaluate_all(
        "(nodes) => nodes.map((node) => node.href)"
    )
    return str(links[0]) if links else ""


def _extract_time(article) -> datetime:
    times = article.locator("time").evaluate_all(
        "(nodes) => nodes.map((node) => node.getAttribute('datetime'))"
    )
    if not times:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(str(times[0]).replace("Z", "+00:00"))


def _extract_author(text: str) -> str:
    match = re.search(r"@[\w_]+", text)
    return match.group(0) if match else ""


def _extract_metrics(text: str) -> dict[str, int]:
    metrics: dict[str, int] = {}
    numbers = [int(value.replace(",", "")) for value in re.findall(r"\b[\d,]{1,9}\b", text)]
    if numbers:
        metrics["largest_visible_number"] = max(numbers)
    return metrics


def _dedupe_items(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    unique: list[Item] = []
    for item in items:
        key = item.stable_key
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
