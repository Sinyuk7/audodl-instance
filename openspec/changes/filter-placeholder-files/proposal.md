# Filter Placeholder Files from Model Lock

## Why

当执行 `sync` 生成 `model-lock.yaml` 时，ComfyUI 自动创建的占位文件（如 `put_checkpoints_here`）被错误地记录为模型文件。这些 0 字节的占位文件：
- 污染了模型清单，增加了 20+ 条无用记录
- 让 `model-lock.yaml` 难以阅读和维护
- 与实际模型文件混在一起，降低了数据质量

## What Changes

在 `scan_models()` 函数中添加过滤逻辑，跳过：
1. 0 字节文件（占位文件的共同特征）
2. 文件名以 `put_` 开头且以 `_here` 结尾的文件（ComfyUI 占位文件命名规则）

## Capabilities

### Modified Capabilities
- `scan_models`: 增强扫描逻辑，自动过滤占位文件

## Impact

- `src/addons/models/lock.py`: 修改 `scan_models()` 函数，添加过滤条件
