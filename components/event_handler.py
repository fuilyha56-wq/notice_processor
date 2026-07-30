"""通知事件处理器。

订阅核心的 ON_RECEIVED_OTHER_MESSAGE 事件，当收到 notice 类型消息时，
按优先级依次调用已注册的处理函数。根据处理器返回的结果决定是否将消息
传递给核心消息流程。
"""

from __future__ import annotations

from typing import Any

from src.app.plugin_system.api.log_api import get_logger
from src.app.plugin_system.base import BaseEventHandler
from src.app.plugin_system.types import EventType
from src.kernel.event import EventDecision

from ..registry import dispatch_notice

logger = get_logger("notice_processor")


class NoticeDispatchEvent(BaseEventHandler):
    """通知分发事件处理器。

    监听 ON_RECEIVED_OTHER_MESSAGE 事件，筛选出 notice 类型的消息，
    然后调用 registry 中已注册的处理函数进行转换。

    处理流程：
    1. 从事件参数中取出原始 envelope（params["raw"]）
    2. 检查 message_info.message_type 是否为 "notice"
    3. 提取 notice_type（来自 extra.notice_type）
    4. 按优先级调用已注册的处理函数
    5. 根据处理器返回值决定行为：
       - 返回 (True, str): 将 str 填入 params["processed"] 交给核心
       - 返回 (False, str): 插件已自行处理，不交给核心
       - 无人处理: 直接丢弃
    """

    name = "notice_dispatch_event"
    description = "通知分发事件处理器 - 将 notice 消息路由至已注册的处理函数"
    weight = 50
    intercept_message = False
    init_subscribe = [EventType.ON_RECEIVED_OTHER_MESSAGE]

    async def execute(
        self, event_name: str, params: dict[str, Any]
    ) -> tuple[EventDecision, dict[str, Any]]:
        """处理 ON_RECEIVED_OTHER_MESSAGE 事件。

        Args:
            event_name: 事件名称
            params: 事件参数，包含:
                - raw: 原始 envelope dict
                - processed: 待填充的处理结果字符串

        Returns:
            (EventDecision, params): 决策与修改后的参数
        """
        try:
            logger.info(f"收到事件 {event_name}，开始处理 notice 消息")
            raw: dict[str, Any] = params.get("raw", {})
            msg_info: dict[str, Any] = raw.get("message_info", {})

            # 仅处理 notice 类型
            message_type = msg_info.get("message_type")
            if message_type != "notice":
                return EventDecision.PASS, params

            # 提取通知子类型
            extra: dict[str, Any] = msg_info.get("extra", {})
            notice_type: str = extra.get("notice_type", "")

            if not notice_type:
                logger.debug("notice 消息缺少 notice_type，丢弃")
                return EventDecision.PASS, params
            logger.debug(f"分发 notice 消息: type={notice_type}, raw={raw}")

            # 分发到已注册的处理函数
            result = await dispatch_notice(notice_type, raw)

            if not result.handled:
                # 没有处理器处理此通知，直接丢弃
                logger.info(f"notice 未被任何处理器处理，已丢弃: type={notice_type}")
                return EventDecision.PASS, params

            if result.pass_to_core:
                # 处理器要求将结果交给核心消息流程
                params["processed"] = result.text
                logger.info(
                    f"notice 已处理并传递给核心: type={notice_type}, "
                    f"text_len={len(result.text)}"
                )
                return EventDecision.SUCCESS, params

            # 处理器已自行消化，不交给核心
            logger.info(
                f"notice 已被处理器自行消化: type={notice_type}, "
                f"text={result.text}"
                f"，不会传递给核心消息流程"
            )
            return EventDecision.SUCCESS, params

        except Exception as e:
            logger.error(f"通知分发处理异常: {e}", exc_info=True)
            return EventDecision.PASS, params
