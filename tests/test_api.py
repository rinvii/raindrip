import pytest
import respx
import json
import httpx
from httpx import Response
from raindrip.api import RaindropAPI, ServerError, RaindropError, RateLimitError
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
async def test_add_raindrop_with_collection(api):
    mock_resp = {"item": {"_id": 100, "link": "http://new.com", "title": "New", "collectionId": 456}}
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.post("/raindrop").mock(return_value=Response(200, json=mock_resp))
        result = await api.add_raindrop("http://new.com", collection_id=456)
        assert result.collection_id == 456

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

@pytest.mark.asyncio
async def test_wayback_error(api):
    async with respx.mock() as respx_mock:
        respx_mock.get("https://archive.org/wayback/available").mock(return_value=Response(500))
        result = await api.check_wayback("http://error.com")
        assert result is None

@pytest.mark.asyncio
async def test_wayback_exception(api):
    async with respx.mock() as respx_mock:
        respx_mock.get("https://archive.org/wayback/available").side_effect = Exception("Boom")
        result = await api.check_wayback("http://exception.com")
        assert result is None

@pytest.mark.asyncio
async def test_get_root_collections(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections").mock(return_value=Response(200, json={"items": [{"_id": 1, "title": "Root"}]}))
        cols = await api.get_root_collections()
        assert len(cols) == 1
        assert cols[0].title == "Root"

@pytest.mark.asyncio
async def test_get_child_collections(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/childrens").mock(return_value=Response(200, json={"items": [{"_id": 2, "title": "Child"}]}))
        cols = await api.get_child_collections()
        assert len(cols) == 1
        assert cols[0].title == "Child"

@pytest.mark.asyncio
async def test_api_retry_server_error(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        route = respx_mock.get("/user")
        route.side_effect = [Response(500), Response(200, json={"user": {"fullName": "Recovered"}})]
        user = await api.get_user()
        assert user["fullName"] == "Recovered"
        assert route.call_count == 2

@pytest.mark.asyncio
async def test_clean_empty_collections(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/collections/clean").mock(return_value=Response(200, json={"count": 3}))
        count = await api.clean_empty_collections()
        assert count == 3

def test_rate_limit_error_init():
    err = RateLimitError(10)
    assert err.status_code == 429
    assert "10s" in str(err)

def test_raindrop_error_hint():
    err = RaindropError("msg", status_code=400, hint="try again")
    assert err.hint == "try again"

@pytest.mark.asyncio
async def test_api_network_error(api):
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").side_effect = httpx.RequestError("Network")
        with pytest.raises(RaindropError) as excinfo:
            await api.get_user()
        assert excinfo.value.status_code == 503

@pytest.mark.asyncio
async def test_api_4xx_no_json(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        # Trigger line 106-107: except Exception: pass
        respx_mock.get("/user").mock(return_value=Response(400, content="Bad Request"))
        with pytest.raises(RaindropError) as excinfo:
            await api.get_user()
        assert "400" in str(excinfo.value)

@pytest.mark.asyncio
async def test_api_max_retries_reached_5xx(api, monkeypatch):
    monkeypatch.setattr(api, "MAX_RETRIES", 1)
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        # Trigger line 116: raise ServerError
        respx_mock.get("/user").mock(return_value=Response(500))
        with pytest.raises(ServerError):
            await api.get_user()

@pytest.mark.asyncio
async def test_api_max_retries_reached_generic(api, monkeypatch):
    # To reach line 132 "Maximum retries exceeded"
    # We need to simulate a case where while loop ends without raising or returning
    # This is tricky because the loop only ends by raising or returning
    # Looking at code: while retries > 0: ... retries -= 1 ...
    # If it falls through, it raises.
    # Let's mock a 429 that keeps repeating
    monkeypatch.setattr(api, "MAX_RETRIES", 1)
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").mock(return_value=Response(429, headers={"Retry-After": "0"}))
        with pytest.raises(RaindropError) as excinfo:
            await api.get_user()
        assert "Maximum retries exceeded" in str(excinfo.value)

@pytest.mark.asyncio
async def test_api_dry_run_with_payload():
    # To cover line 64-65 we need a payload with something that looks like a token
    # and a method that is POST/PUT/DELETE
    api = RaindropAPI(MOCK_TOKEN, dry_run=True)
    # We use a lower-level _request to avoid Pydantic validation of the empty response
    res = await api._request("POST", "/raindrop", json={"title": "Test", "myToken": "secret"})
    assert res["result"] is True

@pytest.mark.asyncio
async def test_api_404_hint(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/999").mock(return_value=Response(404, json={"errorMessage": "Not Found"}))
        with pytest.raises(RaindropError) as excinfo:
            await api.get_raindrop(999)
        assert excinfo.value.status_code == 404
