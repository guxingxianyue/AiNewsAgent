from ainewsagent.domain.models import Source
from ainewsagent.sources.arxiv import parse_arxiv_feed


def test_parse_arxiv_feed():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2601.00001v1</id>
        <updated>2026-01-01T00:00:00Z</updated>
        <published>2026-01-01T00:00:00Z</published>
        <title> Test Paper About Agents </title>
        <summary> A useful abstract. </summary>
        <author><name>Ada Lovelace</name></author>
        <category term="cs.AI" />
        <link title="pdf" href="http://arxiv.org/pdf/2601.00001v1" />
      </entry>
    </feed>
    """

    items = parse_arxiv_feed(xml)

    assert len(items) == 1
    assert items[0].source == Source.ARXIV
    assert items[0].title == "Test Paper About Agents"
    assert items[0].authors == ["Ada Lovelace"]
    assert items[0].categories == ["cs.AI"]
