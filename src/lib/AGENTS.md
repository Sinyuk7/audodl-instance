# src/lib/ Knowledge Base

**Purpose:** Reusable libraries - download strategies, network management, UI

## STRUCTURE

```
lib/
├── download/       # Multi-strategy downloaders
│   ├── __init__.py
│   ├── hf_hub.py   # HuggingFace hub downloads
│   ├── aria2.py    # aria2c multi-threaded
│   └── manifest.yaml
├── network/        # Proxy & network config
│   ├── __init__.py
│   ├── proxy.py    # Mihomo proxy management
│   └── manifest.yaml
├── ui.py           # Terminal UI utilities
└── utils.py        # General utilities
```

## DOWNLOAD STRATEGIES

**HuggingFace (`download/hf_hub.py`):**
- Uses `huggingface_hub` + `hf_xet`
- Version-aware caching
- Token auth via `secrets.yaml`

**CivitAI (`download/aria2.py`):**
- Uses `aria2c` 32-thread
- API token support
- Automatic model info parsing

**Direct URL (`download/aria2.py`):**
- 32 threads, resume support
- Progress tracking via aria2 RPC

## NETWORK MANAGEMENT

**`network/proxy.py`:**
- Mihomo (Clash) proxy setup
- AutoDL academic acceleration
- GitHub/HuggingFace mirror config
- API token injection

**Entry point:** `setup_network()` - must run before any network operation

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add download source | `download/` - New strategy class |
| Modify proxy behavior | `network/proxy.py` |
| Add UI prompt | `ui.py` - Rich/prompt_toolkit helpers |
| Utility functions | `utils.py` |

## CONVENTIONS

**Downloaders:**
- Implement common interface (implicit contract)
- Accept `progress_callback` for UI updates
- Return `Path` to downloaded file
- Handle auth via `secrets.yaml` (not params)

**Network:**
- `setup_network()` is idempotent (safe to call multiple times)
- Caches config to avoid re-initialization
- Use `invalidate_network_cache()` to force reload
