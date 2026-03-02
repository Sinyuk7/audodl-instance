"""
bin/turbo CLI 入口

用法: eval $(python -m src.lib.network)
"""
import os
import sys

from src.lib.network.manager import export_env_shell


def main() -> None:
    output = export_env_shell()
    if output:
        print(output)
        # 提示信息直接输出到 stderr，不经过 eval
        proxy = os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")
        if proxy:
            print(f"[turbo] Proxy: {proxy}", file=sys.stderr)
        else:
            print("[turbo] No proxy", file=sys.stderr)
    else:
        print("[turbo] No network config found", file=sys.stderr)


if __name__ == "__main__":
    main()
