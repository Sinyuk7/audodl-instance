# Task Subsystem Refactor

## Status
**Phase**: Design  
**Created**: 2026-03-06  
**Author**: AI Assistant + User

---

## 1. Problem Statement

### 现状痛点

当前 `TorchAddon.setup()` 包含单一大块逻辑，存在以下问题：

1. **临时修复难以管理**: CUDA JIT 依赖链修复等临时性 fix 与核心安装逻辑混杂
2. **条件执行不灵活**: 无法单独启用/禁用某个子功能
3. **代码膨胀**: 随着 fix 增加，`setup()` 方法会越来越臃肿
4. **复用困难**: 相似的修复逻辑无法在不同场景下复用

### 典型案例 - CUDA JIT Fix

```
PyTorch 底层 JIT（即时编译）机制与 Conda 虚拟环境中破坏的 CUDA 依赖链冲突：
- 破坏源：某些 wheel 包含预编译的 .so 文件，依赖特定 libstdc++.so.6
- 症状：运行时 JIT 编译失败，找不到正确的 GLIBC 符号
- 修复：定位绝对物理地址 + 暴力系统级覆盖 + 脏缓存清理
```

这类修复需要：
- **每次执行检测**（环境随时可能被其他包破坏）
- **内部幂等**（自行判断是否需要修复，而非依赖外部状态标记）
- **可配置开关**（未来问题解决后可关闭）

---

## 2. Design Goals

| 目标 | 描述 |
|------|------|
| **最小侵入** | 扩展现有 `pluggy` 架构，不引入新依赖 |
| **内部幂等** | Task 自行检测环境健康状态，决定是否执行修复 |
| **Addon 边界** | Task 归属于单一 Addon，无跨 Addon Task |
| **配置驱动** | 通过 `manifest.yaml` 控制 Task 启用/禁用 |
| **执行顺序** | 按 `priority` 数值排序（小数优先） |

---

## 3. Design Decisions

### 3.1 实现方案
**选择**: 最小改动方案 - 扩展现有 `pluggy` + `BaseTask` 抽象

**理由**: 
- 不引入新框架依赖
- 复用现有的 `AppContext` 依赖注入
- 与当前架构风格一致

### 3.2 幂等策略
**选择**: 内部幂等（Task 自行检测）

**理由**:
- 环境可能被外部因素破坏（如安装新 pip 包）
- 不能依赖 "上次成功" 的状态标记
- Task 必须检测物理文件系统/环境的实际状态

### 3.3 Task 作用域
**选择**: Addon 内部作用域，无跨 Addon Task

**理由**:
- 职责边界清晰
- 避免复杂的依赖管理
- 若需跨 Addon 能力，应移动 Task 到合适的 Addon

### 3.4 CLI 粒度
**选择**: Addon 级别粒度 (`--only torch_engine`)

**理由**:
- 用户关心的是 "子系统"，不是单个 Task
- Task 级别的 CLI 过于复杂
- 调试时通过 `manifest.yaml` 控制 Task 开关

### 3.5 文件组织
**选择**: 方案 C - 混合模式

```
src/addons/torch_engine/
├── plugin.py           # TorchAddon + 简单内联 Task
├── tasks/              # 复杂 Task 独立文件
│   ├── __init__.py
│   └── cuda_jit_fix.py # FixCudaDependencyChainTask
└── manifest.yaml
```

**理由**:
- 简单 Task（< 30 行）内联，减少文件碎片
- 复杂 Task 独立文件，便于维护和测试
- 灵活应对不同复杂度

### 3.6 TaskResult 粒度
**选择**: 简单三态 `SUCCESS / SKIPPED / FAILED`

**理由**:
- 覆盖所有实际场景
- 与现有 Addon 逻辑风格一致
- 无需过度设计

### 3.7 日志风格
**选择**: 方案 B - 扁平风格

```
>>> [TorchAddon] 开始初始化...
  -> [Task] FixCudaDependencyChain: 检测环境...
  -> [Task] FixCudaDependencyChain: 发现损坏的 libstdc++
  -> [Task] FixCudaDependencyChain: 修复完成 ✓
  -> [Task] DetectCuda: 检测 CUDA 版本...
  -> [Task] DetectCuda: CUDA 12.1 ✓
```

**理由**:
- 与现有 addon 日志风格一致
- 视觉上清晰，易于 grep
- 不引入额外的嵌套层级

---

## 4. Technical Design

### 4.1 Core Abstractions

#### `src/core/task.py`

```python
"""
Task Subsystem - 细粒度任务抽象

提供 Addon 内部的可插拔任务机制，支持：
- 优先级排序执行
- 内部幂等检测
- 配置驱动的启用/禁用
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.core.interface import AppContext


class TaskResult(Enum):
    """Task 执行结果"""
    SUCCESS = "success"   # 执行成功（包括修复成功）
    SKIPPED = "skipped"   # 跳过（环境已健康，无需修复）
    FAILED = "failed"     # 执行失败


@dataclass
class BaseTask(ABC):
    """
    Task 基类
    
    子类必须实现:
    - execute(): 执行任务逻辑，内部自行检测是否需要执行
    """
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = 100  # 小数优先执行
    
    @abstractmethod
    def execute(self, ctx: "AppContext") -> TaskResult:
        """
        执行任务
        
        实现要求:
        1. 内部检测环境状态，决定是否需要执行
        2. 若环境已健康，返回 SKIPPED
        3. 若执行成功，返回 SUCCESS
        4. 若执行失败，返回 FAILED（或抛出异常）
        """
        ...


class TaskRunner:
    """Task 执行器"""
    
    @staticmethod
    def run_tasks(
        tasks: List[BaseTask],
        ctx: "AppContext",
        addon_name: str
    ) -> bool:
        """
        按优先级执行 Task 列表
        
        Args:
            tasks: Task 列表
            ctx: 应用上下文
            addon_name: 所属 Addon 名称（用于日志）
            
        Returns:
            bool: 全部成功返回 True，任一失败返回 False
        """
        from src.core.utils import logger
        
        # 过滤已禁用的 Task
        enabled_tasks = [t for t in tasks if t.enabled]
        if not enabled_tasks:
            return True
        
        # 按优先级排序
        sorted_tasks = sorted(enabled_tasks, key=lambda t: t.priority)
        
        for task in sorted_tasks:
            try:
                result = task.execute(ctx)
                
                if result == TaskResult.SUCCESS:
                    logger.info(f"  -> [Task] {task.name}: 完成 ✓")
                elif result == TaskResult.SKIPPED:
                    logger.info(f"  -> [Task] {task.name}: 跳过 (环境已就绪)")
                elif result == TaskResult.FAILED:
                    logger.error(f"  -> [Task] {task.name}: 失败 ✗")
                    return False
                    
            except Exception as e:
                logger.error(f"  -> [Task] {task.name}: 异常 - {e}")
                if ctx.debug:
                    import traceback
                    traceback.print_exc()
                return False
        
        return True
```

### 4.2 Addon Integration

#### 扩展 `BaseAddon`

```python
# src/core/interface.py

class BaseAddon:
    """Addon 基类"""
    
    module_dir: str = ""
    
    @property
    def name(self) -> str:
        return self.__class__.__name__
    
    def get_tasks(self, phase: str) -> List["BaseTask"]:
        """
        获取指定阶段的 Task 列表
        
        Args:
            phase: 生命周期阶段 ("setup" | "start" | "sync")
            
        Returns:
            该阶段需要执行的 Task 列表
        """
        return []
```

### 4.3 Usage Example - TorchAddon

```python
# src/addons/torch_engine/plugin.py

from src.core.task import BaseTask, TaskResult, TaskRunner

# ══════════════════════════════════════════════════════════════
# 简单 Task - 内联定义
# ══════════════════════════════════════════════════════════════

@dataclass
class DetectCudaTask(BaseTask):
    """检测 CUDA 版本"""
    name: str = "DetectCuda"
    description: str = "检测系统 CUDA 版本"
    priority: int = 10
    
    def execute(self, ctx: AppContext) -> TaskResult:
        # 检测逻辑...
        cuda_version = self._detect_cuda()
        if cuda_version:
            ctx.artifacts.cuda_version = cuda_version
            return TaskResult.SUCCESS
        return TaskResult.FAILED


# ══════════════════════════════════════════════════════════════
# 复杂 Task - 从独立文件导入
# ══════════════════════════════════════════════════════════════

from src.addons.torch_engine.tasks import FixCudaDependencyChainTask


class TorchAddon(BaseAddon):
    module_dir = "torch_engine"
    
    def __init__(self):
        self._setup_tasks: List[BaseTask] = []
        self._init_tasks()
    
    def _init_tasks(self) -> None:
        """初始化 Task 列表"""
        self._setup_tasks = [
            DetectCudaTask(),
            FixCudaDependencyChainTask(
                enabled=True,  # 可从 manifest 读取
                priority=20,
            ),
        ]
    
    def get_tasks(self, phase: str) -> List[BaseTask]:
        if phase == "setup":
            return self._setup_tasks
        return []
    
    @hookimpl
    def setup(self, context: AppContext) -> None:
        logger.info(f"\n>>> [{self.name}] 开始初始化...")
        
        # 执行 setup 阶段的所有 Task
        tasks = self.get_tasks("setup")
        if not TaskRunner.run_tasks(tasks, context, self.name):
            raise RuntimeError(f"[{self.name}] Task 执行失败")
        
        # 其他 setup 逻辑（如果有）...
```

### 4.4 Complex Task Example

```python
# src/addons/torch_engine/tasks/cuda_jit_fix.py

"""
CUDA JIT 依赖链修复

问题背景:
  PyTorch JIT 编译器依赖系统 libstdc++.so.6，但某些 pip 包
  会安装自己的版本到 Conda 环境，导致符号冲突。

修复策略:
  1. 检测 Conda 环境中是否存在问题版本
  2. 定位系统级正确版本的绝对路径
  3. 强制覆盖/软链接
  4. 清理 PyTorch JIT 缓存
"""
from dataclasses import dataclass, field
from pathlib import Path

from src.core.interface import AppContext
from src.core.task import BaseTask, TaskResult
from src.core.utils import logger


@dataclass
class FixCudaDependencyChainTask(BaseTask):
    """修复 CUDA JIT 依赖链"""
    
    name: str = "FixCudaDependencyChain"
    description: str = "修复 Conda 环境中损坏的 CUDA 依赖"
    priority: int = 20
    
    # 配置项
    target_lib: str = "libstdc++.so.6"
    system_lib_path: Path = field(default_factory=lambda: Path("/usr/lib/x86_64-linux-gnu"))
    
    def execute(self, ctx: AppContext) -> TaskResult:
        logger.info(f"  -> [Task] {self.name}: 检测环境...")
        
        # Step 1: 检测是否需要修复
        conda_lib = self._find_conda_lib(ctx)
        if not conda_lib:
            logger.info(f"  -> [Task] {self.name}: 未找到问题库")
            return TaskResult.SKIPPED
        
        if self._is_healthy(conda_lib):
            logger.info(f"  -> [Task] {self.name}: 环境已健康")
            return TaskResult.SKIPPED
        
        # Step 2: 执行修复
        logger.info(f"  -> [Task] {self.name}: 发现损坏的 {self.target_lib}")
        
        system_lib = self.system_lib_path / self.target_lib
        if not system_lib.exists():
            logger.error(f"  -> [Task] {self.name}: 系统库不存在: {system_lib}")
            return TaskResult.FAILED
        
        try:
            # 备份 + 替换
            backup = conda_lib.with_suffix(".bak")
            if not backup.exists():
                conda_lib.rename(backup)
            conda_lib.symlink_to(system_lib)
            
            # 清理 JIT 缓存
            self._clear_jit_cache()
            
            logger.info(f"  -> [Task] {self.name}: 修复完成 ✓")
            return TaskResult.SUCCESS
            
        except OSError as e:
            logger.error(f"  -> [Task] {self.name}: 修复失败 - {e}")
            return TaskResult.FAILED
    
    def _find_conda_lib(self, ctx: AppContext) -> Optional[Path]:
        """定位 Conda 环境中的目标库"""
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if not conda_prefix:
            return None
        lib_path = Path(conda_prefix) / "lib" / self.target_lib
        return lib_path if lib_path.exists() else None
    
    def _is_healthy(self, lib_path: Path) -> bool:
        """检测库是否健康（是否指向系统版本）"""
        if lib_path.is_symlink():
            target = lib_path.resolve()
            return str(self.system_lib_path) in str(target)
        return False
    
    def _clear_jit_cache(self) -> None:
        """清理 PyTorch JIT 缓存"""
        cache_dir = Path.home() / ".cache" / "torch" / "kernels"
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)
            logger.info(f"  -> [Task] {self.name}: 已清理 JIT 缓存")
```

---

## 5. Migration Plan

### Phase 1: Core Infrastructure
1. 创建 `src/core/task.py` - BaseTask, TaskResult, TaskRunner
2. 扩展 `src/core/interface.py` - 添加 `get_tasks()` 方法

### Phase 2: TorchAddon Refactor
1. 创建 `src/addons/torch_engine/tasks/` 目录
2. 提取 CUDA JIT fix 到 `cuda_jit_fix.py`
3. 重构 `TorchAddon.setup()` 使用 TaskRunner

### Phase 3: Validation
1. 在 AutoDL 实例上测试完整流程
2. 验证 Task 启用/禁用功能
3. 验证日志输出格式

---

## 6. Future Extensions

- **manifest.yaml 集成**: 从配置文件读取 Task 的 `enabled` 状态
- **Task 依赖**: 如需要，可添加 `depends_on: List[str]` 字段
- **Dry-run 模式**: `TaskRunner.run_tasks(dry_run=True)` 仅打印计划
- **更多 Addon 迁移**: 逐步将其他 Addon 的复杂逻辑提取为 Task

---

## 7. Addon Task Migration Guide (Template)

> **本章节为通用模板**，用于后续将其他 Addon 迁移到 Task 架构时参考。
> 创建新的迁移 spec 时，可复制此模板并填充具体内容。

### 7.1 迁移前分析清单

在决定是否迁移一个 Addon 到 Task 架构前，回答以下问题：

| 问题 | 答案示例 |
|------|----------|
| Addon 名称 | `NodesAddon` |
| 当前 `setup()` 行数 | 150+ 行 |
| 是否包含临时修复逻辑？ | 是：某些 custom_nodes 的 requirements.txt 修复 |
| 是否有条件执行的子功能？ | 是：部分 nodes 需要特定 CUDA 版本 |
| 子功能之间是否有依赖关系？ | 否（各 node 独立安装） |
| 是否需要配置开关？ | 是：某些实验性 nodes 需要手动启用 |

**迁移建议阈值**：
- `setup()` > 100 行 → 考虑迁移
- 包含 2+ 个独立子功能 → 建议迁移
- 有临时修复逻辑 → 强烈建议迁移

### 7.2 Task 拆分模式

#### 模式 A：功能型拆分
适用于：多个独立子功能并行执行

```
NodesAddon
├── InstallRequiredNodesTask     (priority: 10)
├── InstallOptionalNodesTask     (priority: 20)
└── FixNodeDependenciesTask      (priority: 30)
```

#### 模式 B：阶段型拆分
适用于：有明确的执行阶段

```
ComfyAddon
├── CloneRepositoryTask          (priority: 10)
├── InstallDependenciesTask      (priority: 20)
├── ConfigureExtrasTask          (priority: 30)
└── ValidateInstallationTask     (priority: 40)
```

#### 模式 C：检测-修复型拆分
适用于：环境诊断与修复场景

```
TorchAddon
├── DetectCudaTask               (priority: 10)
├── FixCudaDependencyChainTask   (priority: 20)
├── InstallPyTorchTask           (priority: 30)
└── ValidateTorchCudaTask        (priority: 40)
```

### 7.3 迁移 Spec 模板

创建新的迁移 spec 时，使用以下结构：

```markdown
# {AddonName} Task Migration

## Status
**Phase**: Design
**Parent Spec**: task-subsystem-refactor
**Created**: YYYY-MM-DD

## 1. Current State Analysis

### 现有 setup() 逻辑分解
| 代码段 | 行数 | 功能描述 | 拆分为 Task? |
|--------|------|----------|--------------|
| L10-L30 | 20 | 检测环境 | ✓ DetectXxxTask |
| L31-L80 | 50 | 安装依赖 | ✓ InstallXxxTask |
| L81-L100 | 20 | 临时修复 | ✓ FixXxxTask |
| L101-L110 | 10 | 标记完成 | ✗ 保留在 setup() |

## 2. Proposed Tasks

### Task 1: {TaskName}
- **类型**: 简单/复杂
- **文件**: plugin.py (内联) / tasks/{name}.py
- **优先级**: {number}
- **幂等逻辑**: {检测条件}

### Task 2: ...

## 3. Migration Steps
1. 创建 Task 类
2. 在 `_init_tasks()` 中注册
3. 修改 `setup()` 调用 TaskRunner
4. 移除原有内联逻辑
5. 测试

## 4. Rollback Plan
如果迁移后出现问题，可通过以下方式回滚：
1. 禁用所有 Task: `enabled=False`
2. 恢复原 setup() 逻辑
```

### 7.4 迁移检查清单

- [ ] 分析现有 Addon 逻辑，识别可拆分的 Task
- [ ] 确定每个 Task 的幂等检测逻辑
- [ ] 决定 Task 文件组织（内联 vs 独立文件）
- [ ] 实现 Task 类
- [ ] 修改 Addon 的 `get_tasks()` 方法
- [ ] 修改 `setup()/start()/sync()` 调用 `TaskRunner`
- [ ] 更新 `manifest.yaml` 添加 Task 配置（可选）
- [ ] 测试完整生命周期
- [ ] 文档更新

### 7.5 候选 Addon 迁移优先级

| Addon | 迁移价值 | 复杂度 | 优先级 |
|-------|----------|--------|--------|
| `TorchAddon` | 高（CUDA fix） | 中 | **P0 - 本 spec** |
| `NodesAddon` | 高（多 nodes） | 中 | P1 |
| `ComfyAddon` | 中 | 低 | P2 |
| `UserdataAddon` | 低 | 低 | P3 |
| `SystemAddon` | 低 | 低 | P3 |
| `GitAddon` | 低 | 低 | P3 |
| `ModelAddon` | 中（downloader 已独立） | 低 | P2 |

---

## 7. Acceptance Criteria

- [ ] `BaseTask` 和 `TaskRunner` 实现完成
- [ ] `TorchAddon` 重构完成，CUDA JIT fix 作为独立 Task
- [ ] 日志输出符合扁平风格规范
- [ ] `--only torch_engine` CLI 正常工作
- [ ] 所有 Task 内部幂等（可重复执行无副作用）
