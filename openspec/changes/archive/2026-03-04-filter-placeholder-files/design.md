# Filter Placeholder Files - Design

## Context

`scan_models()` 函数递归扫描 `/root/autodl-tmp/models/` 下所有文件，记录模型信息用于生成 `model-lock.yaml`。

当前已有的过滤机制：
1. 隐藏文件（`.` 开头）- 已跳过
2. 隐藏目录下的文件（如 `.cache/`）- 已跳过  
3. `EXCLUDED_EXTENSIONS` 中的扩展名 - 已跳过

**问题**：ComfyUI 的占位文件（如 `put_checkpoints_here`）没有扩展名，无法被现有机制过滤。

## Goals / Non-Goals

**Goals:**
- 过滤 ComfyUI 占位文件，使 `model-lock.yaml` 只包含真实模型
- 保持向后兼容，不影响现有过滤逻辑
- 代码改动最小化

**Non-Goals:**
- 不改变 lock 文件格式
- 不添加配置文件（硬编码即可，占位文件模式固定）

## Decisions

### Decision 1: 使用双重过滤策略

**方案**：同时检查文件大小和文件名模式

```python
# 新增：跳过 0 字节文件
if model_file.stat().st_size == 0:
    continue

# 新增：跳过 ComfyUI 占位文件 (put_*_here)
if model_file.name.startswith("put_") and model_file.name.endswith("_here"):
    continue
```

**理由**：
- 0 字节检查覆盖了大多数情况
- 文件名模式作为补充，即使文件被意外写入内容也能识别
- 两个条件都是 `continue`，不影响原有逻辑流

### Decision 2: 在 stat() 调用之后检查

将过滤逻辑放在 `stat = model_file.stat()` 之后，复用已获取的 stat 信息，避免额外的文件系统调用。
