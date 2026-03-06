# Task Subsystem Refactor - Implementation Tasks

## Status
**Phase**: Implementation  
**Updated**: 2026-03-06

---

## Task Overview

| # | Task | Status | Priority |
|---|------|--------|----------|
| 1 | 创建 `src/core/task.py` | ✅ DONE | P0 |
| 2 | 扩展 `src/core/interface.py` | ✅ DONE | P0 |
| 3 | 创建 `src/addons/torch_engine/tasks/__init__.py` | ✅ DONE | P0 |
| 4 | 实现 `FixCudaDependencyChainTask` | ✅ DONE | P0 |
| 5 | 重构 `TorchAddon.setup()` | ✅ DONE | P0 |
| 6 | 测试验证 | ⬜ TODO | P1 |

---

## Detailed Tasks

### Task 1: 创建 `src/core/task.py`

**目标**: 实现 Task 子系统的核心抽象

**文件**: `src/core/task.py` (新建)

**内容**:
- `TaskResult` 枚举 (SUCCESS/SKIPPED/FAILED)
- `BaseTask` 抽象基类
- `TaskRunner` 执行器

**验收标准**:
- [ ] 类型注解完整
- [ ] 文档字符串符合项目规范
- [ ] 可被其他模块正常导入

---

### Task 2: 扩展 `src/core/interface.py`

**目标**: 为 `BaseAddon` 添加 `get_tasks()` 方法

**文件**: `src/core/interface.py` (修改)

**变更**:
```python
def get_tasks(self, phase: str) -> List["BaseTask"]:
    """获取指定阶段的 Task 列表"""
    return []
```

**验收标准**:
- [ ] 默认返回空列表（向后兼容）
- [ ] 添加必要的类型导入

---

### Task 3: 创建 `src/addons/torch_engine/tasks/__init__.py`

**目标**: 初始化 tasks 子模块

**文件**: `src/addons/torch_engine/tasks/__init__.py` (新建)

**内容**:
```python
from .cuda_jit_fix import FixCudaDependencyChainTask

__all__ = ["FixCudaDependencyChainTask"]
```

---

### Task 4: 实现 `FixCudaDependencyChainTask`

**目标**: 将 CUDA JIT 修复逻辑封装为独立 Task

**文件**: `src/addons/torch_engine/tasks/cuda_jit_fix.py` (新建)

**功能**:
1. 检测 Conda 环境中的 `libstdc++.so.6`
2. 判断是否指向系统版本
3. 如需修复：备份 → 软链接 → 清理 JIT 缓存

**验收标准**:
- [ ] 内部幂等（可重复执行）
- [ ] 正确返回 SUCCESS/SKIPPED/FAILED
- [ ] 日志符合扁平风格

---

### Task 5: 重构 `TorchAddon.setup()`

**目标**: 使用 TaskRunner 执行 Task 列表

**文件**: `src/addons/torch_engine/plugin.py` (修改)

**变更**:
1. 添加 `_setup_tasks` 属性
2. 添加 `_init_tasks()` 方法
3. 实现 `get_tasks()` 方法
4. 修改 `setup()` 调用 `TaskRunner.run_tasks()`

**验收标准**:
- [ ] 原有功能不变
- [ ] Task 按优先级顺序执行
- [ ] 失败时抛出异常

---

### Task 6: 测试验证

**目标**: 在实际环境中验证 Task 子系统

**测试场景**:
1. 正常执行 `python -m src.main setup`
2. 验证 Task 日志输出格式
3. 验证 SKIPPED 场景（环境已健康）
4. 验证 FAILED 场景（模拟失败）

**验收标准**:
- [ ] 所有场景通过
- [ ] 日志清晰可读
- [ ] 无回归问题

---

## Implementation Order

```
Task 1 (core/task.py)
    ↓
Task 2 (core/interface.py)
    ↓
Task 3 (tasks/__init__.py) ←──┐
    ↓                         │
Task 4 (cuda_jit_fix.py) ─────┘
    ↓
Task 5 (plugin.py 重构)
    ↓
Task 6 (测试验证)
```

---

## Progress Log

| Date | Task | Notes |
|------|------|-------|
| 2026-03-06 | Task 1 | 创建 `src/core/task.py` - TaskResult, BaseTask, TaskRunner |
| 2026-03-06 | Task 2 | 扩展 `src/core/interface.py` - BaseAddon.get_tasks() |
| 2026-03-06 | Task 3 | 创建 `src/addons/torch_engine/tasks/__init__.py` |
| 2026-03-06 | Task 4 | 实现 `FixCudaDependencyChainTask` - CUDA JIT 修复 |
| 2026-03-06 | Task 5 | 重构 `TorchAddon.setup()` - 集成 TaskRunner |
| 2026-03-06 | - | ✅ 所有模块导入验证通过，准备归档 |
