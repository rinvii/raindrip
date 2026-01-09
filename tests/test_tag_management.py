import pytest
import respx
import json
from httpx import Response
from raindrip.api import RaindropAPI

# Mock Data
MOCK_TOKEN = "test-token"
BASE_URL = "https://api.raindrop.io/rest/v1"

@pytest.fixture
def api():
    return RaindropAPI(MOCK_TOKEN)

@pytest.mark.asyncio
async def test_delete_tags(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        delete_route = respx_mock.delete("/tags/0").mock(
            return_value=Response(200, json={"result": True})
        )
        
        success = await api.delete_tags(["old1", "old2"])
        assert success is True
        
        # Verify payload
        payload = json.loads(delete_route.calls.last.request.content)
        assert payload == {"tags": ["old1", "old2"]}

@pytest.mark.asyncio
async def test_rename_tag(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        put_route = respx_mock.put("/tags/0").mock(
            return_value=Response(200, json={"result": True})
        )
        
        success = await api.rename_tag("old", "new")
        assert success is True
        
        # Verify payload
        payload = json.loads(put_route.calls.last.request.content)
        assert payload == {"replace": "new", "tags": ["old"]}
