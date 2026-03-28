import logging
from pathlib import Path
from unittest.mock import MagicMock

from src.addons.models.tasks.migrate_existing_models import (
    MigrateExistingModelsTask,
    MigrationStats,
)
from src.core.task import TaskResult


def test_migrate_skips_ready_symlink_without_scanning(context_with_comfy, monkeypatch):
    task = MigrateExistingModelsTask()
    target_models = context_with_comfy.base_dir / "models"
    target_models.mkdir(parents=True, exist_ok=True)

    comfy_models = MagicMock(spec=Path)
    comfy_models.is_symlink.return_value = True
    comfy_models.resolve.return_value = target_models.resolve()

    monkeypatch.setattr(task, "_get_comfy_models_dir", lambda ctx: comfy_models)
    monkeypatch.setattr(task, "_get_target_models_dir", lambda ctx: target_models)

    migrate_spy = MagicMock()
    monkeypatch.setattr(task, "_migrate_directory_contents", migrate_spy)

    result = task.execute(context_with_comfy)

    assert result == TaskResult.SKIPPED
    migrate_spy.assert_not_called()


def test_migrate_directory_suppresses_auxiliary_conflict_warnings(tmp_path, caplog):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()

    (src / "model.safetensors").write_bytes(b"src-model")
    (dst / "model.safetensors").write_bytes(b"dst-model")
    (src / "README.md").write_text("src readme", encoding="utf-8")
    (dst / "README.md").write_text("dst readme", encoding="utf-8")
    (src / "put_checkpoints_here").write_text("", encoding="utf-8")
    (dst / "put_checkpoints_here").write_text("", encoding="utf-8")
    (src / ".cache.meta").write_text("meta", encoding="utf-8")
    (dst / ".cache.meta").write_text("meta", encoding="utf-8")

    task = MigrateExistingModelsTask()

    with caplog.at_level(logging.INFO, logger="autodl_setup"):
        stats = task._migrate_directory_contents(src, dst)

    assert stats == MigrationStats(migrated=0, model_conflicts=1, auxiliary_conflicts=3)
    assert "model.safetensors" in caplog.text
    assert "README.md" not in caplog.text
    assert "put_checkpoints_here" not in caplog.text
    assert ".cache.meta" not in caplog.text


def test_migrate_keeps_physical_directory_when_conflicts_remain(context_with_comfy, caplog):
    task = MigrateExistingModelsTask()
    comfy_models = context_with_comfy.artifacts.comfy_dir / "models"
    target_models = context_with_comfy.base_dir / "models"
    target_models.mkdir(parents=True, exist_ok=True)

    (comfy_models / "model.safetensors").write_bytes(b"src-model")
    (target_models / "model.safetensors").write_bytes(b"dst-model")

    with caplog.at_level(logging.INFO, logger="autodl_setup"):
        result = task.execute(context_with_comfy)

    assert result == TaskResult.SKIPPED
    assert comfy_models.is_dir()
    assert not comfy_models.is_symlink()
    assert "无法创建软链接" not in caplog.text
    assert "保留物理目录" in caplog.text
