from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ainewsagent.domain.models import Item


@dataclass
class SeenState:
    path: Path
    seen: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, data_dir: Path) -> "SeenState":
        path = data_dir / "seen.json"
        if not path.exists():
            return cls(path=path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(path=path, seen=dict(raw.get("seen", {})))

    def is_seen(self, item: Item) -> bool:
        return item.stable_key in self.seen

    def mark_many(self, items: list[Item]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            self.seen[item.stable_key] = now

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"seen": dict(sorted(self.seen.items()))}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
