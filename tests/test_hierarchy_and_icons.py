import pytest
import respx
import json
from httpx import Response
from raindrip.api import RaindropAPI
from raindrip.models import Collection

# Mock Data
MOCK_TOKEN = "test-token"
BASE_URL = "https://api.raindrop.io/rest/v1"

@pytest.fixture
def api():
    return RaindropAPI(MOCK_TOKEN)

@pytest.mark.asyncio
async def test_get_root_collections(api):
    mock_data = {"items": [{"_id": 1, "title": "Root"}]}
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections").mock(return_value=Response(200, json=mock_data))
        cols = await api.get_root_collections()
        assert len(cols) == 1
        assert cols[0].id == 1

@pytest.mark.asyncio
async def test_get_child_collections(api):
    mock_data = {"items": [{"_id": 2, "title": "Child", "parent": {"$id": 1}}]}
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/childrens").mock(return_value=Response(200, json=mock_data))
        cols = await api.get_child_collections()
        assert len(cols) == 1
        assert cols[0].parent["$id"] == 1

@pytest.mark.asyncio
async def test_search_cover(api):
    mock_data = {
        "items": [
            {"icons": [{"png": "http://icon1.png"}]},
            {"icons": [{"png": "http://icon2.png"}]}
        ]
    }
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/covers/test").mock(return_value=Response(200, json=mock_data))
        icons = await api.search_cover("test")
        assert icons == ["http://icon1.png", "http://icon2.png"]

@pytest.mark.asyncio
async def test_merge_collections(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        put_route = respx_mock.put("/collections/merge").mock(return_value=Response(200, json={"result": True}))
        success = await api.merge_collections([1, 2], 3)
        assert success is True
        payload = json.loads(put_route.calls.last.request.content)
        assert payload == {"ids": [1, 2], "to": 3}

@pytest.mark.asyncio
async def test_clean_empty_collections(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/collections/clean").mock(return_value=Response(200, json={"result": True, "count": 5}))
        count = await api.clean_empty_collections()
        assert count == 5

@pytest.mark.asyncio
async def test_empty_trash(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/collection/-99").mock(return_value=Response(200, json={"result": True}))
        success = await api.empty_trash()
        assert success is True
