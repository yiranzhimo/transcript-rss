import json

import httpx

from transcript_rss.bilibili import _mixin_key, fetch_video_dynamics

NAV_RESPONSE = {
    "data": {
        "wbi_img": {
            "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
            "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png",
        }
    }
}

DYNAMIC_RESPONSE = {
    "code": 0,
    "data": {
        "has_more": False,
        "offset": "",
        "items": [
            {
                "type": "DYNAMIC_TYPE_AV",
                "modules": {
                    "module_author": {"name": "Some UP", "pub_ts": 1_700_000_000},
                    "module_dynamic": {
                        "major": {
                            "type": "MAJOR_TYPE_ARCHIVE",
                            "archive": {
                                "bvid": "BV1abcDEfgh",
                                "title": "A great video",
                                "desc": "video description",
                            },
                        }
                    },
                },
            },
            {
                "type": "DYNAMIC_TYPE_FORWARD",
                "modules": {"module_author": {"name": "Some UP", "pub_ts": 1_700_000_100}},
            },
        ],
    },
}


def test_mixin_key_matches_reference_vector() -> None:
    img_key = "7cd084941338484aae1ad9425b84077c"
    sub_key = "4932caff0ff746eab6f01bf08b70ac45"

    assert _mixin_key(img_key + sub_key) == "ea1db124af3c7062474693fa704f4ff8"


def test_fetch_video_dynamics_signs_request_and_filters_video_items() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "nav" in request.url.path:
            return httpx.Response(200, json=NAV_RESPONSE)
        assert "w_rid" in request.url.params
        assert "wts" in request.url.params
        return httpx.Response(200, json=DYNAMIC_RESPONSE)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        dynamics = fetch_video_dynamics(client, "12345", limit=10)

    assert dynamics == [
        {
            "bvid": "BV1abcDEfgh",
            "title": "A great video",
            "description": "video description",
            "pub_ts": 1_700_000_000,
            "author": "Some UP",
        }
    ]
    assert any("web-dynamic" in str(request.url) for request in requests)
