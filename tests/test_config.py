from __future__ import annotations

import json

import pytest

from portfolio_ops.config import DEFAULT_TARGETS, ConfigurationError, load_targets


def test_loads_targets_from_local_json(tmp_path):
    config_path = tmp_path / "targets.json"
    config_path.write_text(
        json.dumps([{"name": "demo", "url": "https://example.test/path?ignored=1#part"}]),
        encoding="utf-8",
    )

    targets = load_targets(config_path=config_path, environment={})

    assert [(target.name, target.url) for target in targets] == [
        ("demo", "https://example.test/path")
    ]


def test_uses_repository_variable_when_no_local_file():
    targets = load_targets(
        config_path=None,
        environment={
            "MONITOR_TARGETS_JSON": '[{"name": "impact-extension", "url": "https://chromewebstore.google.com/detail/example"}]'
        },
    )

    assert targets[0].name == "impact-extension"
    assert targets[0].url == "https://chromewebstore.google.com/detail/example"


def test_falls_back_to_public_wrepo_target():
    assert load_targets(config_path=None, environment={}) == list(DEFAULT_TARGETS)


def test_rejects_malformed_or_non_public_configuration(tmp_path):
    config_path = tmp_path / "targets.json"
    config_path.write_text('{"name": "not-a-list"}', encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_targets(config_path=config_path, environment={})


def test_rejects_direct_private_network_addresses(tmp_path):
    config_path = tmp_path / "targets.json"
    config_path.write_text('[{"name": "local", "url": "http://127.0.0.1:8000"}]', encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_targets(config_path=config_path, environment={})

    config_path.write_text(
        '[{"name": "private", "url": "https://user:secret@example.test"}]',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        load_targets(config_path=config_path, environment={})
