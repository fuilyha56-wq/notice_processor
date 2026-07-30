"""通知处理器插件入口。

本插件提供通知消息的统一处理框架：
- 通过 Service 暴露注册接口，允许外部插件注册自定义通知处理函数
- 通过 EventHandler 订阅 ON_RECEIVED_OTHER_MESSAGE 事件，将 notice 消息
  路由至已注册的处理函数进行转换

本插件声明对 onebot_expand 的前置依赖，确保 OneBot 能力链路可用。
"""

from src.app.plugin_system.base import BasePlugin, register_plugin

from .components.event_handler import NoticeDispatchEvent
from .components.service import NoticeProcessorService


@register_plugin
class NoticeProcessorPlugin(BasePlugin):
    """通知处理器插件。

    提供通知消息的统一处理框架，允许外部插件通过 Service 注册
    自定义的通知处理函数来响应不同类型的通知事件。

    依赖 onebot_expand 作为 OneBot 能力前置。
    """

    plugin_name = "notice_processor"
    plugin_description = "通知消息统一处理框架，支持外部插件注册自定义通知处理函数"
    plugin_version = "1.0.0"

    configs: list[type] = []
    dependent_components: list[str] = []

    def get_components(self) -> list[type]:
        """返回插件组件类。"""
        return [NoticeDispatchEvent, NoticeProcessorService]
