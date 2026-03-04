# Implementation Tasks

## 1. 修改 scan_models() 函数

- [x] 1.1 在 `stat = model_file.stat()` 之后添加 0 字节文件过滤
- [x] 1.2 添加 `put_*_here` 文件名模式过滤
- [x] 1.3 添加注释说明过滤原因

## 2. 验证

- [x] 2.1 在服务器上执行 `python -m src.main sync --only models` 验证
- [x] 2.2 检查生成的 `model-lock.yaml` 不再包含占位文件

## 验证结果

- 修改前: 43 个模型 (含 20 个占位文件)
- 修改后: 23 个模型 (纯净)
- `grep "put_"` 输出为空 ✓