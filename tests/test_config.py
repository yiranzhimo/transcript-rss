from pathlib import Path

from transcript_rss.config import load_config


def test_site_base_url_can_be_set_by_environment(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
site:
  base_url: https://USERNAME.github.io/transcript-rss
sources:
  - id: example
    type: podcast
    url: https://example.com/feed.xml
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SITE_BASE_URL", "https://owner.github.io/repository")

    config = load_config(path)

    assert config.site.base_url == "https://owner.github.io/repository"
    assert config.sources[0].id == "example"


def test_empty_model_environment_uses_config_value(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
site:
  base_url: https://owner.github.io/repository
translation:
  model: configured/model
sources:
  - id: example
    type: podcast
    url: https://example.com/feed.xml
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENROUTER_MODEL", "")

    config = load_config(path)

    assert config.translation.model == "configured/model"
