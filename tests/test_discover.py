import httpx

from transcript_rss.discover import discover_podcast
from transcript_rss.models import SourceConfig


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Example Show</title>
    <item>
      <guid isPermaLink="false">episode-1</guid>
      <title>Episode One</title>
      <link>https://example.com/episodes/1</link>
      <pubDate>Mon, 27 Jul 2026 01:00:00 GMT</pubDate>
      <enclosure url="https://example.com/audio/1.mp3" type="audio/mpeg"/>
      <podcast:transcript
        url="https://example.com/transcripts/1.vtt"
        type="text/vtt"
        language="en"/>
    </item>
  </channel>
</rss>
"""


def test_discovers_podcast_transcript_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=RSS, headers={"ETag": '"v1"'})

    source = SourceConfig(id="show", type="podcast", url="https://example.com/feed.xml")
    state = {}
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = discover_podcast(source, client, state)

    assert len(items) == 1
    assert items[0].external_id == "episode-1"
    assert items[0].media_url == "https://example.com/audio/1.mp3"
    assert items[0].transcript_links[0].url.endswith("1.vtt")
    assert items[0].transcript_links[0].language == "en"
    assert state["etag"] == '"v1"'
