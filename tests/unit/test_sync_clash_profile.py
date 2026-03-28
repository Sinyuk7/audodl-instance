"""Tests for the local Clash profile sync helper."""
from pathlib import Path

import pytest
import yaml

from scripts.sync_clash_profile import (
    ActiveProfile,
    get_active_profile,
    get_userdata_repo_url,
    write_active_profile,
)


def write_yaml(path: Path, data: dict) -> None:
    """Write a YAML file for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


class TestGetActiveProfile:
    """Active profile selection logic."""

    def test_reads_profile_from_active_index(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        active_file = profiles_dir / "123.yml"
        active_file.parent.mkdir(parents=True, exist_ok=True)
        active_file.write_text("mixed-port: 7890\n", encoding="utf-8")
        (profiles_dir / "456.yml").write_text("mixed-port: 9090\n", encoding="utf-8")
        write_yaml(
            profiles_dir / "list.yml",
            {
                "files": [
                    {"time": "456.yml", "name": "old"},
                    {"time": "123.yml", "name": "active"},
                ],
                "index": 1,
            },
        )

        profile = get_active_profile(profiles_dir)

        assert profile == ActiveProfile(name="active", file_name="123.yml", path=active_file)

    def test_raises_for_invalid_index(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        write_yaml(
            profiles_dir / "list.yml",
            {
                "files": [{"time": "123.yml", "name": "active"}],
                "index": 3,
            },
        )

        with pytest.raises(ValueError):
            get_active_profile(profiles_dir)


class TestManifestConfig:
    """userdata manifest handling."""

    def test_reads_userdata_repo_url(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.yaml"
        write_yaml(manifest, {"userdata_repo": "git@github.com:user/repo.git"})

        assert get_userdata_repo_url(manifest) == "git@github.com:user/repo.git"


class TestWriteActiveProfile:
    """Config file copy behavior."""

    def test_copies_profile_to_mihomo_config(self, tmp_path: Path) -> None:
        source = tmp_path / "profiles" / "active.yml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("mixed-port: 7890\n", encoding="utf-8")
        repo_dir = tmp_path / "backup-repo"
        profile = ActiveProfile(name="active", file_name="active.yml", path=source)

        target = write_active_profile(profile, repo_dir)

        assert target == repo_dir / "mihomo" / "config.yaml"
        assert target.read_text(encoding="utf-8") == "mixed-port: 7890\n"
