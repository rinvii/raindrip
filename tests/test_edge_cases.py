import pytest
import respx
import json
from httpx import Response
from raindrip.api import RaindropAPI, RaindropError

# Mock Data
MOCK_TOKEN = "test-token"
BASE_URL = "https://api.raindrop.io/rest/v1"

@pytest.fixture
def api():
    return RaindropAPI(MOCK_TOKEN)

@pytest.mark.asyncio
async def test_get_nonexistent_raindrop_404(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/999").mock(
            return_value=Response(404, json={"errorMessage": "Not Found"})
        )
        with pytest.raises(RaindropError) as excinfo:
            await api.get_raindrop(999)
        assert excinfo.value.status_code == 404

@pytest.mark.asyncio
async def test_delete_forbidden_collection_403(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/collection/123").mock(
            return_value=Response(403, json={"errorMessage": "Access Denied"})
        )
        with pytest.raises(RaindropError) as excinfo:
            await api.delete_collection(123)
        assert excinfo.value.status_code == 403

@pytest.mark.asyncio
async def test_search_no_results(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrops/0").mock(
            return_value=Response(200, json={"items": []})
        )
        results = await api.search("query-with-no-results")
        assert results == []

@pytest.mark.asyncio
async def test_add_with_special_characters(api):
    special_title = "Title with 🚀 and <script>alert(1)</script>"
    mock_resp = {"item": {"_id": 1, "link": "http://x.com", "title": special_title}}
    
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.post("/raindrop").mock(return_value=Response(200, json=mock_resp))
        result = await api.add_raindrop("http://x.com", title=special_title)
        assert result.title == special_title

@pytest.mark.asyncio
async def test_api_returns_malformed_json(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        # Simulate a 200 OK but with body that isn't JSON
        respx_mock.get("/user").mock(return_value=Response(200, content="Not JSON"))
        with pytest.raises(RaindropError) as excinfo:
            await api.get_user()
        assert "JSON" in str(excinfo.value)

@pytest.mark.asyncio
async def test_batch_delete_empty_list(api):
    # Depending on API, this might error or just return result: true. 
    # We test that our CLI handles the call.
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/raindrops/0").mock(return_value=Response(200, json={"result": True}))
        success = await api.batch_delete_raindrops(0, [])
        assert success is True

@pytest.mark.asyncio
async def test_get_stats_empty_items(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user/stats").mock(return_value=Response(200, json={"items": []}))
        stats = await api.get_stats()
        assert stats == []
