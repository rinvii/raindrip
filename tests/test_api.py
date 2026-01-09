import pytest
import respx
import json
from httpx import Response
from raindrip.api import RaindropAPI, ServerError
from raindrip.models import RaindropUpdate

# Mock Data
MOCK_TOKEN = "test-token"
BASE_URL = "https://api.raindrop.io/rest/v1"

@pytest.fixture
def api():
    return RaindropAPI(MOCK_TOKEN)

@pytest.mark.asyncio
async def test_get_user(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").mock(
            return_value=Response(200, json={"user": {"fullName": "Test User"}})
        )
        user = await api.get_user()
        assert user["fullName"] == "Test User"

@pytest.mark.asyncio
async def test_get_collections(api):
    mock_data = {
        "items": [
            {"_id": 1, "title": "Tech", "count": 10},
            {"_id": 2, "title": "Recipes", "count": 5}
        ]
    }
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/all").mock(return_value=Response(200, json=mock_data))
        collections = await api.get_collections()
        assert len(collections) == 2
        assert collections[0].title == "Tech"

@pytest.mark.asyncio
async def test_get_tags(api):
    mock_data = {"items": [{"_id": "ai", "count": 10}, {"_id": "python", "count": 5}]}
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/tags").mock(return_value=Response(200, json=mock_data))
        tags = await api.get_tags()
        assert tags == ["ai", "python"]

@pytest.mark.asyncio
async def test_pagination(api):
    page1 = {"items": [{"_id": i, "link": f"http://s{i}.com", "title": f"T{i}"} for i in range(50)]}
    page2 = {"items": [{"_id": 99, "link": "http://s99.com", "title": "Last"}]}

    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrops/0", params={"search": "", "page": "0", "perpage": "50"}).mock(
            return_value=Response(200, json=page1)
        )
        respx_mock.get("/raindrops/0", params={"search": "", "page": "1", "perpage": "50"}).mock(
            return_value=Response(200, json=page2)
        )
        results = await api.search(collection_id=0)
        assert len(results) == 51

@pytest.mark.asyncio
async def test_get_raindrop(api):
    mock_item = {"item": {"_id": 123, "title": "Single", "link": "http://one.com"}}
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/123").mock(return_value=Response(200, json=mock_item))
        item = await api.get_raindrop(123)
        assert item.title == "Single"

@pytest.mark.asyncio
async def test_add_raindrop(api):
    mock_resp = {"item": {"_id": 100, "link": "http://new.com", "title": "New", "tags": ["t1"]}}
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        post_route = respx_mock.post("/raindrop").mock(return_value=Response(200, json=mock_resp))
        
        result = await api.add_raindrop("http://new.com", "New", ["t1"])
        assert result.id == 100
        
        # Verify payload
        payload = json.loads(post_route.calls.last.request.content)
        assert payload["link"] == "http://new.com"
        assert payload["tags"] == ["t1"]

@pytest.mark.asyncio
async def test_update_raindrop(api):
    mock_resp = {"item": {"_id": 100, "title": "Updated", "link": "http://example.com"}}
    update_data = RaindropUpdate(title="Updated")
    
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        put_route = respx_mock.put("/raindrop/100").mock(return_value=Response(200, json=mock_resp))
        
        result = await api.update_raindrop(100, update_data)
        assert result.title == "Updated"
        
        # Verify only dirty fields sent
        payload = json.loads(put_route.calls.last.request.content)
        assert payload == {"title": "Updated"}

@pytest.mark.asyncio
async def test_delete_raindrop(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/raindrop/123").mock(return_value=Response(200, json={"result": True}))
        success = await api.delete_raindrop(123)
        assert success is True

@pytest.mark.asyncio
async def test_get_suggestions(api):
    mock_data = {"item": {"tags": [{"_id": "suggested"}], "collections": []}}
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/123/suggest").mock(return_value=Response(200, json=mock_data))
        sug = await api.get_suggestions(123)
        assert sug["tags"][0]["_id"] == "suggested"

@pytest.mark.asyncio
async def test_rate_limit_retry(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        route = respx_mock.get("/user")
        route.side_effect = [
            Response(429, headers={"Retry-After": "0"}), 
            Response(200, json={"user": {}})
        ]
        await api.get_user()
        assert route.call_count == 2

@pytest.mark.asyncio
async def test_server_error_failure(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").mock(return_value=Response(500))
        with pytest.raises(ServerError):
            await api.get_user()

@pytest.mark.asyncio
async def test_wayback_machine(api):
    snapshot = "http://archive.org/web/2023/http://google.com"
    mock_resp = {"archived_snapshots": {"closest": {"url": snapshot, "available": True}}}
    
    async with respx.mock() as respx_mock:
        respx_mock.get("https://archive.org/wayback/available").mock(
            return_value=Response(200, json=mock_resp)
        )
        result = await api.check_wayback("http://google.com")
        assert result == snapshot
