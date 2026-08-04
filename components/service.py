"""通知处理器服务组件。

对外暴露通知处理函数的注册与注销接口，允许其他插件通过 service_api
获取本服务实例后，注册自定义的通知转换函数。

使用示例：
    from src.app.plugin_system.api import service_api

    service = service_api.get_service("notice_processor:service:notice_processor")

    async def my_poke_handler(notice_type: str, envelope: dict) -> str | None:
        if notice_type == "poke":
            extra = envelope.get("message_info", {}).get("extra", {})
            return extra.get("text_description", "")
        return None

    await service.register(
        name="my_poke_handler",
        handler=my_poke_handler,
        notice_types=["poke"],
        priority=10,
    )
"""

from __future__ import annotations

from typing import Any

from src.core.components.base.service import BaseService

from ..registry import (
    NoticeHandlerFunc,
    clear_all_handlers,
    get_registered_handlers,
    register_handler,
    unregister_handler,
)


class NoticeProcessorService(BaseService):
    """通知处理器服务。

    对外提供注册/注销通知转换函数的能力。
    外部插件通过此服务注册自己的 notice 处理逻辑。

    注意：由于 ServiceManager 每次 get_service() 创建新实例，
    实际的注册表维护在模块级 registry 中，本 Service 只是代理调用。
    """

    name: str = "notice_processor"
    description: str = "通知处理器注册服务，允许外部插件注册自定义通知转换函数"
    service_name: str = "notice_processor"
    service_description: str = "通知处理器注册服务，允许外部插件注册自定义通知转换函数"
    version: str = "1.0.0"

    async def register(
        self,
        name: str,
        handler: NoticeHandlerFunc,
        notice_types: list[str] | None = None,
        priority: int = 0,
    ) -> bool:
        """注册一个通知处理函数。

        Args:
            name: 处理器唯一名称，重复注册会覆盖同名处理器
            handler: 异步处理函数，签名为 (notice_type: str, envelope: dict) -> str | None
                - 返回 str: 表示处理成功，该字符串将作为 processed 文本进入核心消息流程
                - 返回 None: 表示此处理器不处理该通知，继续交给下一个处理器
            notice_types: 关注的通知类型列表（如 ["poke", "emoji_like"]），
                为 None 或空列表表示处理所有类型
            priority: 优先级，数值越大越先执行，默认为 0

        Returns:
            注册是否成功
        """
        return await register_handler(
            name=name,
            handler=handler,
            notice_types=notice_types,
            priority=priority,
        )

    async def unregister(self, name: str) -> bool:
        """注销一个通知处理函数。

        Args:
            name: 处理器名称

        Returns:
            是否成功移除
        """
        return await unregister_handler(name)

    def list_handlers(self) -> list[dict[str, Any]]:
        """列出当前所有已注册的处理器信息。

        Returns:
            处理器信息列表，每项包含 name、notice_types、priority
        """
        return get_registered_handlers()

    def clear(self) -> None:
        """清空所有已注册的处理器（慎用）。"""
        clear_all_handlers()
