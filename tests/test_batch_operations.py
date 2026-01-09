import pytest
import respx
import json
from httpx import Response
from raindrip.api import RaindropAPI
from raindrip.models import RaindropUpdate

# Mock Data
MOCK_TOKEN = "test-token"
BASE_URL = "https://api.raindrop.io/rest/v1"

@pytest.fixture
def api():
    return RaindropAPI(MOCK_TOKEN)

@pytest.mark.asyncio
async def test_batch_update(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        put_route = respx_mock.put("/raindrops/0").mock(
            return_value=Response(200, json={"result": True})
        )
        
        update = RaindropUpdate(tags=["batch"])
        success = await api.batch_update_raindrops(0, [1, 2], update)
        assert success is True
        
        # Verify payload
        payload = json.loads(put_route.calls.last.request.content)
        assert payload == {"tags": ["batch"], "ids": [1, 2]}

@pytest.mark.asyncio
async def test_batch_delete(api):
    async with respx.mock(base_url=BASE_URL) as respx_mock:
        delete_route = respx_mock.delete("/raindrops/0").mock(
            return_value=Response(200, json={"result": True})
        )
        
        success = await api.batch_delete_raindrops(0, [1, 2])
        assert success is True
        
        # Verify payload
        payload = json.loads(delete_route.calls.last.request.content)
        assert payload == {"ids": [1, 2]}
