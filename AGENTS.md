# autodl-instance Knowledge Base

**Generated:** 2026-03-31  
**Language:** Python 3.10+  
**Purpose:** AutoDL cloud GPU instance configuration tool for ComfyUI

## OVERVIEW

Plugin-based infrastructure-as-code system for deploying ComfyUI on AutoDL cloud GPU instances. Implements data roaming across instances via Git synchronization.

## STRUCTURE

```
.
├── src/              # Main source (plugin architecture)
│   ├── addons/       # 7 lifecycle plugins
│   ├── core/         # Abstract base classes & ports
│   ├── lib/          # Reusable libraries
│   └── main.py       # Entry point
├── tests/            # unit/ + integration/
├── scripts/          # Shell utilities
├── openspec/         # JSON schemas
├── dcos/             # Docker/config assets
└── init.sh           # Bootstrap entry
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new lifecycle step | `src/addons/*/plugin.py` | Inherit `BaseAddon`, implement setup/start/sync |
| Modify install flow | `src/main.py:create_pipeline()` | Hardcoded plugin order ①→⑦ |
| Shared state between plugins | `src/core/artifacts.py` | `Artifacts` dataclass persists to `.artifacts.json` |
| CLI command dispatch | `src/main.py:execute()` | Handles setup/start/sync actions |
| Network/proxy config | `src/lib/network/` | `setup_network()` must run before all plugins |
| Download strategies | `src/lib/download/` | HuggingFace/CivitAI/aria2 backends |
| Test mocks | `tests/mocks.py` | `MockContext` for unit tests |

## CONVENTIONS

**Plugin Development:**
- Each addon lives in `src/addons/{name}/` with `plugin.py` + `manifest.yaml`
- Plugins declare dependencies via `artifacts` DTO, not direct imports
- Three lifecycle hooks: `setup()` → `start()` → `sync()` (sync runs reverse order)
- State persistence via `ctx.state.mark_completed()` / `is_completed()`

**Configuration:**
- Public params → `manifest.yaml` (scanned at startup)
- Secrets → `secrets.yaml` (gitignored, manual load)
- Cross-instance state → `.artifacts.json` (auto-generated)

**Error Handling:**
- Use `ctx.cmd.run()` not raw `subprocess` (friendly error messages)
- Log to file + terminal via `src.core.utils.logger`

## ANTI-PATTERNS

| DON'T | DO INSTEAD | WHY |
|-------|------------|-----|
| Use `Dict` for context | Use `AppContext` dataclass | Type safety, IDE completion |
| Raw `subprocess.run()` | `ctx.cmd.run()` | Consistent error handling |
| Direct file access for config | `self.get_manifest(ctx)` | Centralized config loading |
| Hardcode paths | Use `ctx.base_dir`, `ctx.comfy_dir` | Portable across environments |
| Skip state checks | Check `ctx.state.is_completed()` | Ensures idempotency |

## COMMANDS

```bash
# Initial setup (run once)
./init.sh [--debug]
# Or directly:
python -m src.main setup [--debug] [--until PLUGIN] [--only PLUGIN]

# Start ComfyUI
python -m src.main start [--debug]

# Sync state before shutdown
python -m src.main sync [--debug]

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## DEPENDENCIES

Core: `pluggy>=1.3.0`, `PyYAML>=6.0.1`, `rich>=13.0.0`, `prompt_toolkit>=3.0.0`

## NOTES

- AutoDL specifics: Data盘 at `/root/autodl-tmp`, System盘 at `/root` (ephemeral)
- Ports 6006/6008 mapped to public by AutoDL
- `uv` used for fast Python package management
- `comfy-cli` manages ComfyUI installation
- All Python processes inherit network config via `setup_network()`
