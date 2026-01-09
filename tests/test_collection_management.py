import pytest
import respx
import json
from httpx import Response
from raindrip.api import RaindropAPI
from raindrip.models import CollectionCreate, CollectionUpdate

# Mock Data
MOCK_TOKEN = "test-token"
BASE_URL = "https://api.raindrop.io/rest/v1"

@pytest.fixture
def api():
    return RaindropAPI(MOCK_TOKEN)

@pytest.mark.asyncio
async def test_create_collection(api):
    mock_resp = {"item": {"_id": 100, "title": "New Col", "count": 0}}
    new_col = CollectionCreate(title="New Col", public=True)
    
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        post_route = respx_mock.post("/collection").mock(return_value=Response(200, json=mock_resp))
        
        result = await api.create_collection(new_col)
        assert result.id == 100
        assert result.title == "New Col"
        
        # Verify payload
        payload = json.loads(post_route.calls.last.request.content)
        assert payload["title"] == "New Col"
        assert payload["public"] is True

@pytest.mark.asyncio
async def test_update_collection(api):
    mock_resp = {"item": {"_id": 100, "title": "Updated Col", "count": 0}}
    update_data = CollectionUpdate(title="Updated Col")
    
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        put_route = respx_mock.put("/collection/100").mock(return_value=Response(200, json=mock_resp))
        
        result = await api.update_collection(100, update_data)
        assert result.title == "Updated Col"
        
        # Verify only dirty fields sent
        payload = json.loads(put_route.calls.last.request.content)
        assert payload == {"title": "Updated Col"}

@pytest.mark.asyncio
async def test_delete_collection(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/collection/100").mock(return_value=Response(200, json={"result": True}))
        success = await api.delete_collection(100)
        assert success is True
