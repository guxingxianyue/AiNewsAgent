from __future__ import annotations

import json
import os
from dataclasses import dataclass
from json import JSONDecodeError

import httpx

from ainewsagent.domain.models import Item, ScoredItem, Source
from ainewsagent.services.ranker import score_item


class LLMConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMClient:
    api_key: str
    base_url: str
    model: str

    @classmethod
    def from_env(cls) -> "LLMClient":
        api_key = os.getenv("MIMO_API_KEY", "")
        base_url = os.getenv("MIMO_BASE_URL", "")
        model = os.getenv("MIMO_MODEL", "")
        missing = [
            name
            for name, value in {
                "MIMO_API_KEY": api_key,
                "MIMO_BASE_URL": base_url,
                "MIMO_MODEL": model,
            }.items()
            if not value
        ]
        if missing:
            raise LLMConfigError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(api_key=api_key, base_url=base_url.rstrip("/"), model=model)

    def score_items(
        self,
        items: list[Item],
        max_items: int,
        *,
        interests: list[str] | None = None,
        avoid_topics: list[str] | None = None,
        reading_level: str = "technical",
    ) -> list[ScoredItem]:
        if not items:
            return []
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 AI 前沿情报筛选员。"
                        "请只返回 JSON，不要返回 Markdown 或解释文字。"
                    ),
                },
                {
                    "role": "user",
                    "content": build_scoring_prompt(
                        items,
                        max_items,
                        interests=interests or [],
                        avoid_topics=avoid_topics or [],
                        reading_level=reading_level,
                    ),
                },
            ],
        }
        try:
            content = self._post_chat(payload)
            decisions = _parse_scoring_response(content)
        except Exception:
            decisions = {}
        scored = []
        for index, item in enumerate(items, start=1):
            decision = decisions.get(index, {})
            rule_score = score_item(item)
            llm_score = _bounded_float(decision.get("score", 0), minimum=0, maximum=10)
            topic = str(decision.get("topic") or _fallback_topic(item))
            reason = str(decision.get("reason") or "规则筛选命中，模型评分缺失。")
            importance = _clean_choice(str(decision.get("importance") or ""), {"必读", "值得扫读", "可跳过"}, "值得扫读")
            audience = str(decision.get("audience") or _fallback_audience(reading_level))
            tags = _string_list(decision.get("tags"))[:5]
            scored.append(
                ScoredItem(
                    item=item,
                    rule_score=rule_score,
                    llm_score=llm_score,
                    topic=topic,
                    reason=reason,
                    importance=importance,
                    audience=audience,
                    tags=tags,
                )
            )
        return sorted(scored, key=lambda scored_item: scored_item.total_score, reverse=True)[:max_items]

    def create_briefing(self, items: list[Item], failures: list[str]) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是资深 AI 研究与产业情报分析师。"
                        "请用简洁中文生成每日 AI 前沿简报，重视准确性、来源链接和为什么重要。"
                    ),
                },
                {"role": "user", "content": build_prompt(items, failures)},
            ],
        }
        return self._post_chat(payload)

    def create_briefing_from_scored(self, scored_items: list[ScoredItem], failures: list[str]) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是资深 AI 研究与产业情报分析师。"
                        "请用简洁中文生成每日 AI 前沿简报，重视准确性、来源链接和为什么重要。"
                    ),
                },
                {"role": "user", "content": build_scored_prompt(scored_items, failures)},
            ],
        }
        return self._post_chat(payload)

    def _post_chat(self, payload: dict) -> str:
        with httpx.Client(timeout=90.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Mimo response did not contain choices[0].message.content") from exc


def build_scoring_prompt(
    items: list[Item],
    max_items: int,
    *,
    interests: list[str] | None = None,
    avoid_topics: list[str] | None = None,
    reading_level: str = "technical",
) -> str:
    interests = interests or []
    avoid_topics = avoid_topics or []
    lines = [
        "请从候选材料中评估哪些最值得进入每日 AI 前沿简报。",
        f"最多选择 {max_items} 条，但请对所有候选都给出评分。",
        "请优先贴合用户兴趣，降低用户明确不想看的主题权重。",
        f"用户兴趣：{', '.join(interests) if interests else '通用 AI 前沿'}",
        f"避免主题：{', '.join(avoid_topics) if avoid_topics else '无'}",
        f"阅读深度：{reading_level}",
        "返回严格 JSON，格式如下：",
        '{"items":[{"index":1,"score":8.5,"topic":"智能体","importance":"必读","audience":"Agent 开发者","tags":["推理","开源"],"reason":"一句中文理由"}]}',
        "score 范围 0-10；importance 只能是 必读/值得扫读/可跳过；topic 用 2-8 个中文字概括；reason 不超过 40 个中文字。",
        "\n候选材料：",
    ]
    for index, item in enumerate(items, start=1):
        source = "X" if item.source == Source.X else "arXiv"
        authors = ", ".join(item.authors[:4])
        categories = ", ".join(item.categories[:5])
        lines.extend(
            [
                f"\n[{index}] 来源：{source}",
                f"标题：{item.title}",
                f"作者/账号：{authors or '未知'}",
                f"分类：{categories or '无'}",
                f"时间：{item.published_at.isoformat()}",
                f"链接：{item.url}",
                f"内容：{item.text[:900]}",
            ]
        )
    return "\n".join(lines)


def build_prompt(items: list[Item], failures: list[str]) -> str:
    lines = [
        "请根据以下候选材料生成中文 Markdown 晨报。",
        "固定结构：今日重点、X 热点、arXiv 论文精选、交叉趋势/观察、原始链接列表。",
        "要求：精选 10-15 条；每条说明一句为什么重要；不要编造候选材料外的信息。",
    ]
    if failures:
        lines.append("采集失败信息：" + "；".join(failures))
    lines.append("\n候选材料：")
    for index, item in enumerate(items, start=1):
        source = "X" if item.source == Source.X else "arXiv"
        authors = ", ".join(item.authors[:4])
        categories = ", ".join(item.categories[:5])
        lines.extend(
            [
                f"\n[{index}] 来源：{source}",
                f"标题：{item.title}",
                f"作者/账号：{authors or '未知'}",
                f"分类：{categories or '无'}",
                f"时间：{item.published_at.isoformat()}",
                f"链接：{item.url}",
                f"内容：{item.text[:1200]}",
            ]
        )
    return "\n".join(lines)


def build_scored_prompt(scored_items: list[ScoredItem], failures: list[str]) -> str:
    lines = [
        "请根据以下已经筛选和评分的材料生成中文 Markdown 晨报。",
        "固定结构：今日重点、X 热点、arXiv 论文精选、交叉趋势/观察、原始链接列表。",
        "要求：精选 10-15 条；每条说明为什么重要；优先使用评分理由；不要编造候选材料外的信息。",
    ]
    if failures:
        lines.append("采集失败信息：" + "；".join(failures))
    lines.append("\n候选材料：")
    for index, scored in enumerate(scored_items, start=1):
        item = scored.item
        source = "X" if item.source == Source.X else "arXiv"
        authors = ", ".join(item.authors[:4])
        categories = ", ".join(item.categories[:5])
        lines.extend(
            [
                f"\n[{index}] 来源：{source}",
                f"标题：{item.title}",
                f"作者/账号：{authors or '未知'}",
                f"分类：{categories or '无'}",
                f"评分：规则分 {scored.rule_score:.1f}，模型分 {scored.llm_score:.1f}，总分 {scored.total_score:.1f}",
                f"主题：{scored.topic}",
                f"重要性：{scored.importance}",
                f"适合读者：{scored.audience}",
                f"标签：{', '.join(scored.tags) if scored.tags else '无'}",
                f"入选理由：{scored.reason}",
                f"时间：{item.published_at.isoformat()}",
                f"链接：{item.url}",
                f"内容：{item.text[:1200]}",
            ]
        )
    return "\n".join(lines)


def _parse_scoring_response(content: str) -> dict[int, dict]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        payload = json.loads(text)
    except JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        payload = json.loads(text[start : end + 1])
    decisions: dict[int, dict] = {}
    for raw in payload.get("items", []):
        try:
            decisions[int(raw["index"])] = raw
        except (KeyError, TypeError, ValueError):
            continue
    return decisions


def _bounded_float(value, *, minimum: float, maximum: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return minimum
    return min(max(numeric, minimum), maximum)


def _fallback_topic(item: Item) -> str:
    if item.categories:
        return item.categories[0]
    return "AI 动态" if item.source == Source.X else "论文"


def _fallback_audience(reading_level: str) -> str:
    if reading_level == "executive":
        return "决策者"
    if reading_level == "product":
        return "产品/业务读者"
    return "技术读者"


def _clean_choice(value: str, choices: set[str], fallback: str) -> str:
    return value if value in choices else fallback


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
