import httpx
import pytest
from backend.app.services import attraction_intro as intro


@pytest.mark.parametrize('text', [
    '黄鹤楼是位于湖北省武汉市的著名历史建筑，也是江南三大名楼之一。',
    '大雁塔（又名慈恩寺塔）位于陕西省西安市，是唐代佛教建筑的代表之一。',
    '黄鹤楼是位于武汉市的一座具有悠久历史的文化名楼也是重要的城市地标建筑。',
])
def test_excerpt_is_short(text):
    value = intro.short_intro(text)
    assert 20 <= len(value) <= 30
    assert '（' not in value


@pytest.mark.asyncio
@pytest.mark.parametrize('city,ambiguous,fail,expected', [
    ('武汉', False, False, True), ('西安', False, False, False),
    ('武汉', True, False, False), ('武汉', False, True, False),
])
async def test_verified_city_source_failure_and_cache(monkeypatch, city, ambiguous, fail, expected):
    intro._cache.clear()
    intro._limit = __import__('asyncio').Semaphore(3)
    calls = []

    async def get(self, url, **kwargs):
        calls.append(kwargs)
        if fail:
            raise httpx.ConnectError('unavailable')
        return httpx.Response(200, request=httpx.Request('GET', url), json={'query': {'pages': [{
            'extract': '黄鹤楼位于湖北省武汉市，是江南三大名楼之一，历史悠久。',
            'fullurl': 'https://zh.wikipedia.org/wiki/黄鹤楼',
            'pageprops': {'disambiguation': ''} if ambiguous else {},
        }]}})

    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    result = await intro.get_attraction_intro('黄鹤楼', city)
    assert bool(result) is expected
    assert await intro.get_attraction_intro('黄鹤楼', city) == result
    assert len(calls) == 1
    if expected:
        assert len(result['summary']) <= 30
        assert result['license'] == 'CC BY-SA 4.0'


@pytest.mark.asyncio
async def test_parenthesized_alias_uses_same_request_and_checks_city(monkeypatch):
    intro._cache.clear()
    intro._limit = __import__('asyncio').Semaphore(3)
    async def get(self, url, **kwargs):
        assert kwargs['params']['titles'] == '宿舍旧址(博文女校)|博文女校'
        return httpx.Response(200, request=httpx.Request('GET', url), json={'query': {'pages': [
            {'missing': True},
            {'title': '博文女校', 'extract': '博文女校位于上海市，是历史建筑与中共一大代表的住地。',
             'fullurl': 'https://zh.wikipedia.org/wiki/博文女校'},
        ]}})
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    assert (await intro.get_attraction_intro('宿舍旧址(博文女校)', '上海'))['summary']
    assert not await intro.get_attraction_intro('宿舍旧址(博文女校)', '深圳')
