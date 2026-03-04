# scan_models 过滤增强

## MODIFIED Requirements

### Requirement: 跳过占位文件

`scan_models()` 函数在递归扫描模型目录时，应自动跳过 ComfyUI 生成的占位提示文件。

#### Scenario: 过滤 0 字节文件

- **WHEN** 扫描到一个文件大小为 0 字节
- **THEN** 跳过该文件，不将其加入结果列表
- **AND** 不计算其 hash 值

#### Scenario: 过滤 put_*_here 命名模式

- **WHEN** 扫描到文件名以 `put_` 开头且以 `_here` 结尾
- **THEN** 跳过该文件，不将其加入结果列表

#### Scenario: 正常模型文件不受影响

- **WHEN** 扫描到有效的模型文件（如 `.safetensors`, `.gguf`）
- **AND** 文件大小 > 0
- **THEN** 正常记录该文件到结果列表

### Requirement: 向后兼容

过滤逻辑不应破坏现有功能。

#### Scenario: 已有的扩展名过滤继续生效

- **WHEN** 扫描到 `.yaml`, `.json`, `.txt` 等已排除扩展名的文件
- **THEN** 继续跳过这些文件（与之前行为一致）
