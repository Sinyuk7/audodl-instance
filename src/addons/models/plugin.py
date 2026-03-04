"""
Models Addon - ComfyUI 模型目录管理
负责 models/ 目录软链接、模型迁移、sync 时生成模型快照
"""
import shutil
from pathlib import Path

from src.core.interface import BaseAddon, AppContext, hookimpl
from src.core.utils import logger
from src.lib.utils import load_yaml, save_yaml


class ModelAddon(BaseAddon):
    """ComfyUI 模型目录管理插件
    
    核心职责：
    1. Setup: 将 ComfyUI/models/ 软链接到数据盘 (autodl-tmp/models/)
    2. Sync: 检查软链接状态，迁移残留文件，生成模型快照
    """
    
    module_dir = "models"
    MODELS_DIR_NAME = "models"  # ComfyUI 原生目录名

    def _get_target_models_dir(self, ctx: AppContext) -> Path:
        """获取数据盘上的模型目录路径"""
        return ctx.base_dir / self.MODELS_DIR_NAME

    def _get_comfy_models_dir(self, ctx: AppContext) -> Path:
        """获取 ComfyUI 的 models 目录路径"""
        comfy_dir = ctx.artifacts.comfy_dir
        if not comfy_dir:
            raise RuntimeError("ComfyUI 目录未初始化")
        return comfy_dir / self.MODELS_DIR_NAME

    def _migrate_directory_contents(self, src: Path, dst: Path) -> int:
        """将 src 目录内容迁移到 dst，冲突时跳过
        
        Args:
            src: 源目录
            dst: 目标目录
            
        Returns:
            迁移的文件数量
        """
        migrated = 0
        
        if not src.exists() or not src.is_dir():
            return migrated
        
        for item in src.iterdir():
            target = dst / item.name
            
            if item.is_file():
                if target.exists():
                    logger.warning(f"  -> [SKIP] 文件已存在，跳过: {item.name}")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(item), str(target))
                    logger.info(f"  -> 迁移文件: {item.name}")
                    migrated += 1
            
            elif item.is_dir():
                # 跳过空目录
                if not any(item.rglob("*")):
                    continue
                # 递归迁移子目录
                target.mkdir(parents=True, exist_ok=True)
                migrated += self._migrate_directory_contents(item, target)
        
        return migrated

    def _setup_models_symlink(self, ctx: AppContext) -> bool:
        """建立 models/ 软链接
        
        Returns:
            True 如果创建了新链接或进行了迁移
        """
        comfy_models = self._get_comfy_models_dir(ctx)
        target_models = self._get_target_models_dir(ctx)
        
        # 确保目标目录存在
        if not target_models.exists():
            target_models.mkdir(parents=True, exist_ok=True)
            logger.info(f"  -> 创建模型目录: {target_models}")
        
        # Case 1: 已是正确的软链接
        if comfy_models.is_symlink():
            if comfy_models.resolve() == target_models.resolve():
                logger.info(f"  -> models 软链接已就绪 → {target_models}")
                return False
            else:
                # 软链接指向错误位置，删除重建
                logger.warning(f"  -> models 软链接指向错误，重建...")
                comfy_models.unlink()
        
        # Case 2: 是物理目录，需要迁移内容
        elif comfy_models.is_dir():
            logger.info(f"  -> 检测到 models 物理目录，开始迁移...")
            migrated = self._migrate_directory_contents(comfy_models, target_models)
            if migrated > 0:
                logger.info(f"  -> 已迁移 {migrated} 个文件到数据盘")
            
            # 删除原目录（包括可能剩余的空子目录）
            shutil.rmtree(comfy_models)
            logger.info(f"  -> 已删除原 models 目录")
        
        # Case 3: 路径不存在（正常情况）
        elif comfy_models.exists():
            # 是文件？不应该出现
            logger.warning(f"  -> [WARN] models 路径是文件，删除...")
            comfy_models.unlink()
        
        # 创建软链接
        try:
            comfy_models.symlink_to(target_models)
            logger.info(f"  -> models 软链接已创建 → {target_models}")
            return True
        except OSError as e:
            # Windows 需要管理员权限创建软链接
            logger.warning(f"  -> [SKIP] 无法创建软链接（需管理员权限）: {e}")
            return False

    def _check_and_migrate_orphan_files(self, ctx: AppContext) -> int:
        """检查并迁移残留在 ComfyUI 原生目录的文件
        
        某些节点可能在软链接断开时下载文件到物理目录，
        此方法在 sync 时检查并迁移这些文件。
        
        Returns:
            迁移的文件数量
        """
        comfy_models = self._get_comfy_models_dir(ctx)
        target_models = self._get_target_models_dir(ctx)
        
        # 如果是正确的软链接，无需处理
        if comfy_models.is_symlink():
            if comfy_models.resolve() == target_models.resolve():
                return 0
            # 软链接指向错误，重建
            logger.warning(f"  -> [WARN] models 软链接指向错误，重建...")
            comfy_models.unlink()
            comfy_models.symlink_to(target_models)
            return 0
        
        # 如果变成了物理目录，迁移内容
        if comfy_models.is_dir():
            logger.info(f"  -> [WARN] 检测到 models 变为物理目录，迁移残留文件...")
            migrated = self._migrate_directory_contents(comfy_models, target_models)
            
            # 删除并重建软链接
            shutil.rmtree(comfy_models)
            comfy_models.symlink_to(target_models)
            logger.info(f"  -> 已重建 models 软链接")
            
            return migrated
        
        return 0

    @hookimpl
    def setup(self, context: AppContext) -> None:
        """初始化钩子：建立 models/ 软链接"""
        logger.info("\n>>> [Models] 开始初始化模型目录...")
        ctx = context

        comfy_dir = ctx.artifacts.comfy_dir
        if not comfy_dir or not comfy_dir.exists():
            logger.warning(f"  -> [WARN] ComfyUI 目录不存在，跳过 models 配置")
            return

        target_models = self._get_target_models_dir(ctx)
        logger.info(f"  -> 目标模型目录: {target_models}")

        # 建立软链接
        self._setup_models_symlink(ctx)
        
        # 产出
        ctx.artifacts.models_dir = target_models

    @hookimpl
    def start(self, context: AppContext) -> None:
        """启动钩子：无操作"""
        pass

    @hookimpl
    def sync(self, context: AppContext) -> None:
        """同步钩子：检查软链接、迁移残留文件、生成模型快照"""
        from src.addons.models.lock import generate_snapshot, cleanup_orphan_metas
        from src.addons.models.config import LOCK_FILE

        logger.info("\n>>> [Models] 开始同步模型数据...")

        models_dir = context.artifacts.models_dir
        if not models_dir:
            models_dir = self._get_target_models_dir(context)
        
        if not models_dir.exists():
            logger.warning("  -> [WARN] 模型目录不存在，跳过")
            return

        # 1. 检查并迁移残留文件（软链接可能断开）
        try:
            migrated = self._check_and_migrate_orphan_files(context)
            if migrated > 0:
                logger.info(f"  -> 已迁移 {migrated} 个残留文件")
        except Exception as e:
            logger.warning(f"  -> [WARN] 检查残留文件失败: {e}")

        # 2. 清理孤儿 .meta 文件
        cleaned = cleanup_orphan_metas(models_dir)
        if cleaned > 0:
            logger.info(f"  -> 已清理 {cleaned} 个孤儿 .meta 文件")

        # 3. 加载上一次 lock (用于增量 hash)
        previous_lock = load_yaml(LOCK_FILE)

        # 4. 生成快照
        snapshot = generate_snapshot(models_dir, previous_lock)

        model_count = len(snapshot.get("models", []))
        if model_count == 0:
            logger.info("  -> 模型目录为空，跳过快照写入")
            return

        # 5. 写入 model-lock.yaml
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        save_yaml(LOCK_FILE, snapshot)
        logger.info(f"  -> 快照已保存: {LOCK_FILE} ({model_count} 个模型)")