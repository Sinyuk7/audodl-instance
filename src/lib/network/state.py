"""
网络初始化状态缓存 - 跨进程共享

将网络初始化的决策结果（用 mihomo 还是 turbo）和订阅更新结果
缓存到 /tmp 目录下的 JSON 文件，避免每次 model download 等
短生命周期进程都重复走完整的初始化流程。

状态文件生命周期:
- 写入: setup_network() 完成后
- 读取: 后续进程的 setup_network() 开始时
- 过期: 默认 30 分钟（订阅失败缓存）/ 60 分钟（整体决策缓存）
- 清理: 系统重启自动清理 (/tmp)

设计原则:
- 状态文件仅用于加速，不影响正确性（过期 / 损坏 / 缺失均安全退化）
- 使用 /tmp 目录，实例关机后自动清理，不污染数据盘
"""
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("autodl_setup")

# 状态文件路径（/tmp 在实例关机后自动清理）
_STATE_FILE = Path("/tmp/autodl_network_state.json")

# 缓存有效期（秒）
SUBSCRIPTION_FAIL_TTL = 30 * 60   # 订阅失败缓存: 30 分钟内不再重试
NETWORK_DECISION_TTL = 60 * 60    # 网络决策缓存: 60 分钟内复用


def _read_state() -> Dict[str, Any]:
    """安全读取状态文件"""
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return {}


def _write_state(state: Dict[str, Any]) -> None:
    """安全写入状态文件（合并更新）"""
    try:
        existing = _read_state()
        existing.update(state)
        _STATE_FILE.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.debug(f"  -> 状态缓存写入失败 (不影响功能): {e}")


def is_subscription_recently_failed() -> bool:
    """检查订阅更新是否在短时间内失败过

    Returns:
        True 表示最近 SUBSCRIPTION_FAIL_TTL 秒内有过订阅失败记录
    """
    state = _read_state()
    fail_ts = state.get("subscription_fail_ts")
    if fail_ts is None:
        return False
    return (time.time() - fail_ts) < SUBSCRIPTION_FAIL_TTL


def mark_subscription_failed() -> None:
    """记录订阅更新失败"""
    _write_state({"subscription_fail_ts": time.time()})


def mark_subscription_success() -> None:
    """清除订阅失败标记"""
    _write_state({"subscription_fail_ts": None})


def get_cached_network_decision() -> Optional[str]:
    """获取缓存的网络决策

    Returns:
        "mihomo" / "turbo" / None (无缓存或已过期)
    """
    state = _read_state()
    decision = state.get("network_decision")
    decision_ts = state.get("network_decision_ts")

    if decision is None or decision_ts is None:
        return None

    if (time.time() - decision_ts) > NETWORK_DECISION_TTL:
        return None

    return decision


def cache_network_decision(decision: str) -> None:
    """缓存网络初始化的最终决策

    Args:
        decision: "mihomo" 或 "turbo"
    """
    _write_state({
        "network_decision": decision,
        "network_decision_ts": time.time(),
    })


def invalidate_cache() -> None:
    """清除所有缓存状态（供手动重置或 setup 生命周期使用）"""
    try:
        _STATE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
