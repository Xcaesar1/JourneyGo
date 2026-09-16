"""高德地图MCP服务封装"""

from typing import Any

from hello_agents.tools import MCPTool

from ..config import get_settings
from ..models.schemas import Location, WeatherInfo
from .attraction_discovery import AmapAttractionDiscoveryProvider

# 全局MCP工具实例
_amap_mcp_tool = None


def get_amap_mcp_tool() -> MCPTool:
    """
    获取高德地图MCP工具实例(单例模式)

    Returns:
        MCPTool实例
    """
    global _amap_mcp_tool

    if _amap_mcp_tool is None:
        settings = get_settings()

        if not settings.vite_amap_web_key:
            raise ValueError("高德地图 API Key 未配置，请先在前端设置页完成配置")

        # 创建MCP工具
        _amap_mcp_tool = MCPTool(
            name="amap",
            description="高德地图服务,支持POI搜索、路线规划、天气查询等功能",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.vite_amap_web_key},
            auto_expand=True,  # 自动展开为独立工具
        )

        print("✅ 高德地图MCP工具初始化成功")
        print(f"   工具数量: {len(_amap_mcp_tool._available_tools)}")

        # 打印可用工具列表
        if _amap_mcp_tool._available_tools:
            print("   可用工具:")
            for tool in _amap_mcp_tool._available_tools[:5]:  # 只打印前5个
                print(f"     - {tool.get('name', 'unknown')}")
            if len(_amap_mcp_tool._available_tools) > 5:
                print(f"     ... 还有 {len(_amap_mcp_tool._available_tools) - 5} 个工具")

    return _amap_mcp_tool


class AmapService:
    """高德地图服务封装类"""

    def __init__(self):
        """初始化服务"""
        settings = get_settings()
        self._poi_provider = (
            AmapAttractionDiscoveryProvider(settings.vite_amap_web_key)
            if settings.vite_amap_web_key
            else None
        )

    @property
    def mcp_tool(self) -> MCPTool:
        """Initialize the legacy map MCP only when a route/weather call needs it."""
        return get_amap_mcp_tool()

    def search_poi(self, keywords: str, city: str, citylimit: bool = True) -> list[dict[str, Any]]:
        """
        搜索POI

        Args:
            keywords: 搜索关键词
            city: 城市
            citylimit: 是否限制在城市范围内

        Returns:
            POI信息列表
        """
        _ = citylimit
        if self._poi_provider is None:
            return []
        page = self._poi_provider.discover(city, interests=[keywords], limit=40)
        return [item.model_dump(mode="json") for item in page.items]

    def get_weather(self, city: str) -> list[WeatherInfo]:
        """
        查询天气

        Args:
            city: 城市名称

        Returns:
            天气信息列表
        """
        try:
            # 调用MCP工具
            result = self.mcp_tool.run(
                {"action": "call_tool", "tool_name": "maps_weather", "arguments": {"city": city}}
            )

            print(f"天气查询结果: {result[:200]}...")

            # TODO: 解析实际的天气数据
            return []

        except Exception as e:
            print(f"❌ 天气查询失败: {str(e)}")
            return []

    def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: str | None = None,
        destination_city: str | None = None,
        route_type: str = "walking",
    ) -> dict[str, Any]:
        """
        规划路线

        Args:
            origin_address: 起点地址
            destination_address: 终点地址
            origin_city: 起点城市
            destination_city: 终点城市
            route_type: 路线类型 (walking/driving/transit)

        Returns:
            路线信息
        """
        try:
            # 根据路线类型选择工具
            tool_map = {
                "walking": "maps_direction_walking_by_address",
                "driving": "maps_direction_driving_by_address",
                "transit": "maps_direction_transit_integrated_by_address",
            }

            tool_name = tool_map.get(route_type, "maps_direction_walking_by_address")

            # 构建参数
            arguments = {
                "origin_address": origin_address,
                "destination_address": destination_address,
            }

            # 公共交通需要城市参数
            if route_type == "transit":
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city
            else:
                # 其他路线类型也可以提供城市参数提高准确性
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city

            # 调用MCP工具
            result = self.mcp_tool.run(
                {"action": "call_tool", "tool_name": tool_name, "arguments": arguments}
            )

            print(f"路线规划结果: {result[:200]}...")

            # TODO: 解析实际的路线数据
            return {}

        except Exception as e:
            print(f"❌ 路线规划失败: {str(e)}")
            return {}

    def geocode(self, address: str, city: str | None = None) -> Location | None:
        """
        地理编码(地址转坐标)

        Args:
            address: 地址
            city: 城市

        Returns:
            经纬度坐标
        """
        try:
            arguments = {"address": address}
            if city:
                arguments["city"] = city

            result = self.mcp_tool.run(
                {"action": "call_tool", "tool_name": "maps_geo", "arguments": arguments}
            )

            print(f"地理编码结果: {result[:200]}...")

            # TODO: 解析实际的坐标数据
            return None

        except Exception as e:
            print(f"❌ 地理编码失败: {str(e)}")
            return None

    def get_poi_detail(self, poi_id: str) -> dict[str, Any]:
        """
        获取POI详情

        Args:
            poi_id: POI ID

        Returns:
            POI详情信息
        """
        if self._poi_provider is None:
            return {}
        item = self._poi_provider.get_detail(poi_id)
        return item.model_dump(mode="json") if item is not None else {}


# 创建全局服务实例
_amap_service = None


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service

    if _amap_service is None:
        _amap_service = AmapService()

    return _amap_service


def reset_amap_service() -> None:
    """重置高德地图服务与 MCP 工具实例（用于运行时配置更新后热生效）。"""
    global _amap_service, _amap_mcp_tool
    _amap_service = None
    _amap_mcp_tool = None
