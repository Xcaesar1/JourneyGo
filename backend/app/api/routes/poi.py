"""POI相关API路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import get_settings
from ...services.amap_service import get_amap_service
from ...services.attraction_discovery import AmapAttractionDiscoveryProvider
from ...services.attraction_images import build_attraction_image_service

router = APIRouter(prefix="/poi", tags=["POI"])


class POIDetailResponse(BaseModel):
    """POI详情响应"""

    success: bool
    message: str
    data: dict | None = None


@router.get(
    "/detail/{poi_id}",
    response_model=POIDetailResponse,
    summary="获取POI详情",
    description="根据POI ID获取详细信息,包括图片",
)
async def get_poi_detail(poi_id: str):
    """
    获取POI详情

    Args:
        poi_id: POI ID

    Returns:
        POI详情响应
    """
    try:
        amap_service = get_amap_service()

        # 调用高德地图POI详情API
        result = amap_service.get_poi_detail(poi_id)

        return POIDetailResponse(success=True, message="获取POI详情成功", data=result)

    except Exception as e:
        print(f"❌ 获取POI详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取POI详情失败: {str(e)}")


@router.get("/search", summary="搜索POI", description="根据关键词搜索POI")
async def search_poi(keywords: str, city: str = "北京"):
    """
    搜索POI

    Args:
        keywords: 搜索关键词
        city: 城市名称

    Returns:
        搜索结果
    """
    try:
        amap_service = get_amap_service()
        result = amap_service.search_poi(keywords, city)

        return {"success": True, "message": "搜索成功", "data": result}

    except Exception as e:
        print(f"❌ 搜索POI失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索POI失败: {str(e)}")


@router.get(
    "/photo", summary="获取景点图片", description="按高德、Openverse、本地占位图顺序解析景点图片"
)
async def get_attraction_photo(
    name: str,
    city: str | None = None,
    poi_id: str | None = None,
):
    """
    获取景点图片

    Args:
        name: 景点名称
        city: 所在城市

    Returns:
        图片URL
    """
    settings = get_settings()
    amap_provider = (
        AmapAttractionDiscoveryProvider(settings.vite_amap_web_key)
        if settings.vite_amap_web_key
        else None
    )
    service = build_attraction_image_service(amap_provider)
    image = await service.resolve(poi_id=poi_id or "", name=name, city=city or "")
    return {
        "success": True,
        "message": "获取图片成功",
        "data": {
            "name": name,
            "poi_id": poi_id or "",
            "photo_url": image.url,
            "image_url": image.url,
            "source": image.source,
            "author": image.author,
            "license": image.license,
            "source_page": image.source_page,
            "attribution": image.attribution,
        },
    }
