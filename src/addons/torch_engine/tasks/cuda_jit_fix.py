"""
CUDA JIT 依赖链修复

问题背景:
    PyTorch JIT 编译器依赖系统 libstdc++.so.6，但某些 pip 包
    会安装自己的版本到 Conda 环境，导致符号冲突。
    
    症状:
    - RuntimeError: CUDA error: JIT compilation failed
    - undefined symbol: _ZSt28__throw_bad_array_new_lengthv
    - GLIBCXX_3.4.xx not found
    
修复策略:
    1. 检测 Conda 环境中是否存在问题版本
    2. 判断是否已链接到系统版本（幂等检测）
    3. 如需修复：备份 → 软链接 → 清理 JIT 缓存
"""
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.core.interface import AppContext
from src.core.task import BaseTask, TaskResult
from src.core.utils import logger


@dataclass
class FixCudaDependencyChainTask(BaseTask):
    """修复 CUDA JIT 依赖链"""
    
    name: str = "FixCudaDependencyChain"
    description: str = "修复 Conda 环境中损坏的 CUDA 依赖"
    priority: int = 5  # 在 Torch 安装之前执行
    
    # 配置项 - 可通过构造函数覆盖
    target_lib: str = "libstdc++.so.6"
    system_lib_path: Path = field(
        default_factory=lambda: Path("/usr/lib/x86_64-linux-gnu")
    )
    
    def execute(self, ctx: AppContext) -> TaskResult:
        """
        执行 CUDA 依赖链修复
        
        内部幂等：
        - 检测 Conda 环境中的目标库
        - 若已链接到系统版本，返回 SKIPPED
        - 若需要修复，执行修复并返回 SUCCESS
        """
        logger.info(f"  -> [Task] {self.name}: 检测环境...")
        
        # Step 1: 定位 Conda 环境中的目标库
        conda_lib = self._find_conda_lib()
        if not conda_lib:
            logger.info(f"  -> [Task] {self.name}: 未检测到 Conda 环境或目标库")
            return TaskResult.SKIPPED
        
        # Step 2: 检测是否已健康
        if self._is_healthy(conda_lib):
            logger.info(f"  -> [Task] {self.name}: 环境已健康 (已链接到系统版本)")
            return TaskResult.SKIPPED
        
        # Step 3: 执行修复
        logger.info(f"  -> [Task] {self.name}: 发现问题库 {conda_lib}")
        
        system_lib = self.system_lib_path / self.target_lib
        if not system_lib.exists():
            logger.warning(
                f"  -> [Task] {self.name}: 系统库不存在 {system_lib}，无法修复"
            )
            # 不是致命错误，可能是非 Debian 系系统
            return TaskResult.SKIPPED
        
        try:
            # 备份原文件（如果不是软链接）
            if not conda_lib.is_symlink():
                backup = conda_lib.with_suffix(f"{conda_lib.suffix}.bak")
                if not backup.exists():
                    logger.info(f"  -> [Task] {self.name}: 备份 {conda_lib.name} -> {backup.name}")
                    shutil.copy2(conda_lib, backup)
                # 删除原文件
                conda_lib.unlink()
            else:
                # 已是软链接但指向错误位置，删除重建
                conda_lib.unlink()
            
            # 创建软链接到系统版本
            conda_lib.symlink_to(system_lib)
            logger.info(f"  -> [Task] {self.name}: 已链接 {conda_lib} -> {system_lib}")
            
            # 清理 PyTorch JIT 缓存
            self._clear_jit_cache()
            
            return TaskResult.SUCCESS
            
        except PermissionError as e:
            logger.error(f"  -> [Task] {self.name}: 权限不足 - {e}")
            return TaskResult.FAILED
        except OSError as e:
            logger.error(f"  -> [Task] {self.name}: 文件操作失败 - {e}")
            return TaskResult.FAILED
    
    def _find_conda_lib(self) -> Optional[Path]:
        """
        定位 Conda 环境中的目标库
        
        Returns:
            库文件路径，若不存在返回 None
        """
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if not conda_prefix:
            return None
        
        lib_path = Path(conda_prefix) / "lib" / self.target_lib
        return lib_path if lib_path.exists() or lib_path.is_symlink() else None
    
    def _is_healthy(self, lib_path: Path) -> bool:
        """
        检测库是否健康
        
        健康条件：是软链接且指向系统版本目录
        
        Args:
            lib_path: 库文件路径
            
        Returns:
            是否健康
        """
        if not lib_path.is_symlink():
            return False
        
        try:
            target = lib_path.resolve()
            # 检查是否指向系统库目录
            return str(self.system_lib_path) in str(target.parent)
        except OSError:
            return False
    
    def _clear_jit_cache(self) -> None:
        """清理 PyTorch JIT 编译缓存"""
        cache_dirs = [
            Path.home() / ".cache" / "torch" / "kernels",
            Path.home() / ".cache" / "torch_extensions",
        ]
        
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    logger.info(f"  -> [Task] {self.name}: 已清理缓存 {cache_dir}")
                except Exception as e:
                    logger.warning(f"  -> [Task] {self.name}: 清理缓存失败 {cache_dir}: {e}")
