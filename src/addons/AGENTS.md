# src/addons/ Knowledge Base

**Purpose:** Lifecycle plugins - each manages one domain of the setup process

## STRUCTURE

```
addons/
├── system/          # ① UV, cache migration to data盘
├── git_config/      # ② Git/SSH setup
├── torch_engine/    # ③ PyTorch CUDA installation
├── comfy_core/      # ④ ComfyUI core install
├── userdata/        # ⑤ User data directory symlinks
├── nodes/           # ⑥ Custom nodes (ComfyUI-Manager)
└── models/          # ⑦ Model download & management
```

## PLUGIN TEMPLATE

```python
# src/addons/my_feature/plugin.py
from src.core.interface import BaseAddon, AppContext

class MyAddon(BaseAddon):
    def setup(self, ctx: AppContext) -> None:
        # Check if already done
        if ctx.state.is_completed("MY_FEATURE"):
            return
        # ... do work ...
        ctx.state.mark_completed("MY_FEATURE")
    
    def start(self, ctx: AppContext) -> None:
        pass  # Or implement if needed
    
    def sync(self, ctx: AppContext) -> None:
        pass  # Or implement cleanup/persistence
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Install system tools | `system/plugin.py` - UV, comfy-cli, cache links |
| Configure Git/SSH | `git_config/plugin.py` - Keys, user.name, user.email |
| PyTorch setup | `torch_engine/plugin.py` - CUDA version detection |
| ComfyUI install | `comfy_core/plugin.py` - Uses `comfy-cli` |
| User data sync | `userdata/plugin.py` - Git push/pull for roaming |
| Node management | `nodes/plugin.py` - ComfyUI-Manager integration |
| Model downloads | `models/plugin.py` - HuggingFace/CivitAI handlers |

## CONVENTIONS

**Each addon directory contains:**
- `plugin.py` - Implementation (required)
- `manifest.yaml` - Public configuration (required)
- `schema.py` - Pydantic models for manifest (optional)
- `tasks/` - Sub-tasks for complex addons (optional)
- `secrets.yaml` - Private credentials (gitignored, optional)
- `secrets.yaml.example` - Template for secrets (required if secrets.yaml exists)

**State Management:**
- Always check `ctx.state.is_completed(StateKey.X)` before work
- Mark completion with `ctx.state.mark_completed(StateKey.X)`
- State persists across runs in `BASE_DIR/.state/`

**Artifacts (cross-plugin data):**
- Write: `ctx.artifacts.my_field = value`
- Read: `value = ctx.artifacts.my_field`
- Persisted automatically after setup completes
