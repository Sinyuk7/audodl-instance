"""Sync the active local Clash profile into the backup repo and push it."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILES_DIR = Path.home() / ".config" / "clash" / "profiles"
DEFAULT_REPO_DIR = PROJECT_ROOT / "my-comfyui-backup"
USERDATA_MANIFEST = PROJECT_ROOT / "src" / "addons" / "userdata" / "manifest.yaml"
TARGET_CONFIG_RELATIVE = Path("mihomo") / "config.yaml"


@dataclass(frozen=True)
class ActiveProfile:
    """Metadata for the currently selected Clash profile."""

    name: str
    file_name: str
    path: Path


def load_yaml(path: Path) -> dict:
    """Load a YAML document from disk."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def get_userdata_repo_url(manifest_path: Path) -> str:
    """Read the backup repo URL from userdata manifest configuration."""
    data = load_yaml(manifest_path)
    return str(data.get("userdata_repo", "")).strip()


def get_active_profile(profiles_dir: Path) -> ActiveProfile:
    """Resolve the current Clash profile using list.yml's active index."""
    list_file = profiles_dir / "list.yml"
    if not list_file.exists():
        raise FileNotFoundError(f"Clash profile index not found: {list_file}")

    data = load_yaml(list_file)
    files = data.get("files")
    index = data.get("index")

    if not isinstance(files, list) or not files:
        raise ValueError(f"No Clash profiles declared in {list_file}")
    if not isinstance(index, int) or index < 0 or index >= len(files):
        raise ValueError(f"Invalid active Clash profile index in {list_file}: {index}")

    entry = files[index]
    file_name = str(entry.get("time", "")).strip()
    if not file_name:
        raise ValueError(f"Active Clash profile entry is missing its file name in {list_file}")

    profile_path = profiles_dir / file_name
    if not profile_path.exists():
        raise FileNotFoundError(f"Active Clash profile file not found: {profile_path}")

    return ActiveProfile(
        name=str(entry.get("name", file_name)).strip() or file_name,
        file_name=file_name,
        path=profile_path,
    )


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command and capture output."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def ensure_backup_repo(repo_dir: Path, repo_url: str) -> None:
    """Make sure the backup directory is a git clone of the configured repo."""
    if (repo_dir / ".git").exists():
        return

    if not repo_url:
        raise RuntimeError(
            f"{repo_dir} is not a git repo, and userdata_repo is not configured in {USERDATA_MANIFEST}"
        )

    if repo_dir.exists() and any(repo_dir.iterdir()):
        backup_root = Path(tempfile.gettempdir()) / "autodl-instance-backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_dir = backup_root / f"{repo_dir.name}_{datetime.now():%Y%m%d_%H%M%S}"
        shutil.move(str(repo_dir), str(backup_dir))
        print(f"Backed up existing non-git directory to {backup_dir}")

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    clone = subprocess.run(
        ["git", "clone", repo_url, str(repo_dir)],
        text=True,
        capture_output=True,
        check=False,
    )
    if clone.returncode != 0:
        raise RuntimeError(f"git clone failed: {clone.stderr.strip() or clone.stdout.strip()}")


def write_active_profile(profile: ActiveProfile, repo_dir: Path) -> Path:
    """Copy the active Clash profile into the backup repo's mihomo config file."""
    target = repo_dir / TARGET_CONFIG_RELATIVE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(profile.path, target)
    return target


def has_staged_or_worktree_changes(repo_dir: Path, target: Path) -> bool:
    """Check whether the target file differs in the git worktree."""
    status = run_git(["status", "--porcelain", "--", str(target.relative_to(repo_dir))], repo_dir)
    if status.returncode != 0:
        raise RuntimeError(f"git status failed: {status.stderr.strip() or status.stdout.strip()}")
    return bool(status.stdout.strip())


def commit_and_push(repo_dir: Path, target: Path, message: str) -> bool:
    """Commit and push the synced config if the target file changed."""
    relative_target = str(target.relative_to(repo_dir))
    add = run_git(["add", "--", relative_target], repo_dir)
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr.strip() or add.stdout.strip()}")

    diff = run_git(["diff", "--cached", "--quiet", "--", relative_target], repo_dir)
    if diff.returncode == 0:
        return False
    if diff.returncode not in (0, 1):
        raise RuntimeError(f"git diff failed: {diff.stderr.strip() or diff.stdout.strip()}")

    commit = run_git(["commit", "-m", message, "--", relative_target], repo_dir)
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip() or commit.stdout.strip()}")

    push = run_git(["push"], repo_dir)
    if push.returncode != 0:
        raise RuntimeError(f"git push failed: {push.stderr.strip() or push.stdout.strip()}")
    return True


def build_commit_message(profile: ActiveProfile) -> str:
    """Create a concise commit message for profile syncs."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"Sync mihomo config from {profile.name} at {timestamp}"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Sync the current local Clash profile into my-comfyui-backup/mihomo/config.yaml",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=DEFAULT_PROFILES_DIR,
        help=f"Clash profiles directory (default: {DEFAULT_PROFILES_DIR})",
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=DEFAULT_REPO_DIR,
        help=f"Backup repo directory (default: {DEFAULT_REPO_DIR})",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=USERDATA_MANIFEST,
        help=f"userdata manifest path (default: {USERDATA_MANIFEST})",
    )
    parser.add_argument(
        "--message",
        type=str,
        default="",
        help="Optional git commit message override",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Only update the file locally without committing or pushing",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    profiles_dir = args.profiles_dir.expanduser().resolve()
    repo_dir = args.repo_dir.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()

    profile = get_active_profile(profiles_dir)
    repo_url = get_userdata_repo_url(manifest_path) if manifest_path.exists() else ""

    print(f"Active Clash profile: {profile.name} ({profile.file_name})")
    ensure_backup_repo(repo_dir, repo_url)
    target = write_active_profile(profile, repo_dir)
    print(f"Updated {target}")

    if args.no_push:
        print("Skipping git commit/push because --no-push was provided")
        return 0

    if not has_staged_or_worktree_changes(repo_dir, target):
        print("No config changes detected; nothing to commit")
        return 0

    message = args.message or build_commit_message(profile)
    changed = commit_and_push(repo_dir, target, message)
    if changed:
        print("Committed and pushed mihomo config update")
    else:
        print("No staged diff detected; nothing pushed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
