"""通知处理函数注册表。

本模块维护一个模块级的注册表，存储外部插件注册的通知转换函数。
由于 ServiceManager.get_service() 每次创建新实例，
注册表必须在模块级维护以保证跨调用共享状态。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from src.app.plugin_system.api.log_api import get_logger

logger = get_logger("notice_processor")

# 通知处理函数的类型签名：
# 接收 notice_type (str) 和 envelope (dict)
# 返回值：
#   - None: 不处理此通知，交给下一个处理器
#   - (True, str): 处理完成，将 str 交给核心消息流程（填入 processed）
#   - (False, str): 处理完成但不交给核心（插件自行消化），str 为日志用途
NoticeHandlerFunc = Callable[[str, dict[str, Any]], Awaitable[tuple[bool, str] | None]]


@dataclass(slots=True)
class NoticeHandlerEntry:
    """注册的通知处理函数条目。

    Attributes:
        name: 处理器名称，用于标识和去重
        handler: 异步处理函数
        notice_types: 该处理器关注的通知类型列表，为空表示处理所有类型
        priority: 优先级，数值越大越先执行
    """

    name: str
    handler: NoticeHandlerFunc
    notice_types: list[str] = field(default_factory=list)
    priority: int = 0


@dataclass(slots=True)
class DispatchResult:
    """分发结果。

    Attributes:
        handled: 是否有处理器处理了此通知
        pass_to_core: 是否需要将结果传递给核心消息流程
        text: 处理后的文本
    """

    handled: bool
    pass_to_core: bool
    text: str


# 模块级注册表：所有已注册的通知处理器
_handlers: list[NoticeHandlerEntry] = []
_lock: asyncio.Lock = asyncio.Lock()


async def register_handler(
    name: str,
    handler: NoticeHandlerFunc,
    notice_types: list[str] | None = None,
    priority: int = 0,
) -> bool:
    """注册一个通知处理函数。

    Args:
        name: 处理器唯一名称，重复注册会覆盖已有的同名处理器
        handler: 异步处理函数，签名为 (notice_type: str, envelope: dict) -> tuple[bool, str] | None
            - 返回 None: 不处理，继续交给下一个处理器
            - 返回 (True, str): 处理完成，str 将交给核心消息流程
            - 返回 (False, str): 处理完成但不交给核心，插件自行消化
        notice_types: 关注的通知类型列表，为 None 或空列表表示处理所有类型
        priority: 优先级，数值越大越先执行，默认为 0

    Returns:
        注册是否成功
    """
    async with _lock:
        # 移除同名的旧处理器
        _handlers[:] = [h for h in _handlers if h.name != name]

        entry = NoticeHandlerEntry(
            name=name,
            handler=handler,
            notice_types=notice_types or [],
            priority=priority,
        )
        _handlers.append(entry)
        # 按优先级降序排列
        _handlers.sort(key=lambda e: e.priority, reverse=True)

    logger.info(f"已注册通知处理器: name={name}, types={notice_types or '全部'}, priority={priority}")
    return True


async def unregister_handler(name: str) -> bool:
    """注销一个通知处理函数。

    Args:
        name: 处理器名称

    Returns:
        是否成功移除（未找到同名处理器时返回 False）
    """
    async with _lock:
        before_count = len(_handlers)
        _handlers[:] = [h for h in _handlers if h.name != name]
        removed = len(_handlers) < before_count

    if removed:
        logger.info(f"已注销通知处理器: name={name}")
    else:
        logger.debug(f"未找到通知处理器: name={name}")
    return removed


async def dispatch_notice(notice_type: str, envelope: dict[str, Any]) -> DispatchResult:
    """将通知分发给所有匹配的处理器。

    按优先级从高到低依次调用。第一个返回非 None 结果的处理器将终止分发。

    Args:
        notice_type: 通知类型（如 "poke", "emoji_like", "group_ban" 等）
        envelope: 完整的 MessageEnvelope 字典

    Returns:
        DispatchResult: 分发结果
    """
    async with _lock:
        snapshot = list(_handlers)

    for entry in snapshot:
        # 检查该处理器是否关注此通知类型
        if entry.notice_types and notice_type not in entry.notice_types:
            continue

        try:
            result = await entry.handler(notice_type, envelope)
            if result is not None:
                pass_to_core, text = result
                logger.debug(
                    f"通知被处理器 '{entry.name}' 处理: type={notice_type}, "
                    f"pass_to_core={pass_to_core}, text_len={len(text)}"
                )
                return DispatchResult(handled=True, pass_to_core=pass_to_core, text=text)
        except Exception as e:
            logger.error(f"通知处理器 '{entry.name}' 执行异常: {e}", exc_info=True)

    return DispatchResult(handled=False, pass_to_core=False, text="")


def get_registered_handlers() -> list[dict[str, Any]]:
    """获取当前所有已注册处理器的信息（只读）。

    Returns:
        处理器信息列表
    """
    return [
        {
            "name": entry.name,
            "notice_types": entry.notice_types,
            "priority": entry.priority,
        }
        for entry in _handlers
    ]


def clear_all_handlers() -> None:
    """清空所有已注册的处理器（仅供测试或插件卸载时使用）。"""
    _handlers.clear()
    logger.info("已清空所有通知处理器")
