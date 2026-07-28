from pathlib import Path

from transcript_rss import cli


def _write_config(path: Path) -> None:
    path.write_text(
        """
site:
  base_url: https://owner.github.io/repository
sources:
  - id: source-a
    type: podcast
    url: https://example.com/a
  - id: source-b
    type: podcast
    url: https://example.com/b
""",
        encoding="utf-8",
    )


def test_sync_can_select_one_source_and_write_an_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    artifact_dir = tmp_path / "artifact"
    _write_config(config_path)
    received = {}

    def fake_run_sync(config, fail_on_error=False, artifact_dir=None):
        received["source_ids"] = [source.id for source in config.sources]
        received["fail_on_error"] = fail_on_error
        received["artifact_dir"] = artifact_dir
        return {"discovered": 0, "published": 0, "failed": 0, "skipped": 0}

    monkeypatch.setattr(cli, "run_sync", fake_run_sync)

    result = cli.main(
        [
            "--config",
            str(config_path),
            "sync",
            "--source",
            "source-b",
            "--artifact-dir",
            str(artifact_dir),
        ]
    )

    assert result == 0
    assert received == {
        "source_ids": ["source-b"],
        "fail_on_error": False,
        "artifact_dir": artifact_dir.resolve(),
    }


def test_sync_rejects_an_unknown_source(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)

    result = cli.main(
        [
            "--config",
            str(config_path),
            "sync",
            "--source",
            "missing",
        ]
    )

    assert result == 2
    assert "unknown source id: missing" in capsys.readouterr().err
