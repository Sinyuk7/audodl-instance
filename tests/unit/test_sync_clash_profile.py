"""Tests for the local Clash profile sync helper."""
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.sync_clash_profile import (
    ActiveProfile,
    commit_and_push,
    get_active_profile,
    get_userdata_repo_url,
    push_current_branch,
    sync_repo_with_remote,
    write_active_profile,
)


def write_yaml(path: Path, data: dict) -> None:
    """Write a YAML file for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def git_result(code: int = 0, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    """Build a fake git subprocess result for monkeypatch-driven tests."""
    return subprocess.CompletedProcess(args=["git"], returncode=code, stdout=out, stderr=err)


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


class TestGitRecovery:
    """Sync helper git resiliency behaviors."""

    def test_sync_repo_stashes_and_restores_local_changes(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        calls: list[list[str]] = []
        responses = [
            git_result(out=" M foo.txt\n"),  # status --porcelain
            git_result(out="Saved working directory and index state"),  # stash push
            git_result(out="origin/main"),  # rev-parse @{upstream}
            git_result(out="Already up to date."),  # pull --rebase
            git_result(out="Dropped refs/stash@{0}"),  # stash pop
        ]

        def fake_run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            assert cwd == repo_dir
            calls.append(args)
            return responses.pop(0)

        monkeypatch.setattr("scripts.sync_clash_profile.run_git", fake_run_git)

        sync_repo_with_remote(repo_dir, reason="test-sync")

        assert ["stash", "push", "-u", "-m", "test-sync"] in calls
        assert ["stash", "pop"] in calls
        assert not responses

    def test_commit_and_push_retries_after_remote_reject(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        target = repo_dir / "mihomo" / "config.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("mixed-port: 7890\n", encoding="utf-8")

        calls: list[list[str]] = []
        responses = [
            git_result(),  # add
            git_result(code=1),  # diff --cached --quiet -> has staged changes
            git_result(),  # commit
            git_result(code=1, err="! [rejected] main -> main (non-fast-forward)"),  # push fail
            git_result(out=""),  # status --porcelain during sync
            git_result(out="origin/main"),  # rev-parse @{upstream}
            git_result(out="Already up to date."),  # pull --rebase
            git_result(),  # push retry success
        ]

        def fake_run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            assert cwd == repo_dir
            calls.append(args)
            return responses.pop(0)

        monkeypatch.setattr("scripts.sync_clash_profile.run_git", fake_run_git)

        changed = commit_and_push(repo_dir, target, "sync config")

        assert changed is True
        assert calls.count(["push"]) == 2
        assert ["pull", "--rebase"] in calls
        assert not responses

    def test_push_current_branch_sets_upstream_when_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        responses = [
            git_result(code=1, err="fatal: The current branch main has no upstream branch."),
            git_result(out="origin\n"),
            git_result(),
        ]

        def fake_run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            assert cwd == repo_dir
            return responses.pop(0)

        monkeypatch.setattr("scripts.sync_clash_profile.run_git", fake_run_git)

        result = push_current_branch(repo_dir)

        assert result.returncode == 0
        assert not responses
