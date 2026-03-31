# src/ Knowledge Base

**Purpose:** Main source directory - plugin architecture implementation

## STRUCTURE

```
src/
├── main.py          # CLI entry & pipeline orchestration
├── addons/          # 7 lifecycle plugins
├── core/            # Abstract base classes, ports, adapters
└── lib/             # Reusable libraries (download, network)
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add plugin to pipeline | `main.py:create_pipeline()` - append to list |
| Change plugin order | `main.py:create_pipeline()` - reorder list |
| Access manifest config | `main.py:load_manifests()` or `addon.get_manifest(ctx)` |
| CLI argument parsing | `main.py:main()` - argparse setup |
| Context creation | `main.py:create_context()` |

## PLUGIN PIPELINE

Hardcoded execution order (setup) / reverse (sync):

1. `system` - UV package manager, cache migration
2. `git_config` - Git/SSH credentials
3. `torch_engine` - PyTorch CUDA setup
4. `comfy_core` - ComfyUI installation
5. `userdata` - User data symlinks
6. `nodes` - Custom nodes management
7. `models` - Model download/management

## CONVENTIONS

- Plugins are classes in `addons/{name}/plugin.py`
- Must inherit `BaseAddon` from `core.interface`
- Must implement `setup()`, `start()`, `sync()` methods
- Plugin name = directory name (accessed via `self.name`)
