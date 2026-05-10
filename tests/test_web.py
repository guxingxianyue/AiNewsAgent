from fastapi.testclient import TestClient

from ainewsagent.infrastructure.config import Settings
from ainewsagent.interfaces.web import create_app


def test_web_home_without_briefing(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data"))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "还没有简报" in response.text


def test_web_items_has_filters(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data"))
    client = TestClient(app)

    response = client.get("/items?q=agent&source=arxiv")

    assert response.status_code == 200
    assert "搜索标题" in response.text
    assert "全部来源" in response.text
