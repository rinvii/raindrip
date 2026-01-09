import json
import pytest
from typer.testing import CliRunner
import respx
from httpx import Response
from raindrip.main import app
from raindrip.config import Config, save_config

runner = CliRunner()
BASE_URL = "https://api.raindrop.io/rest/v1"

@pytest.fixture(autouse=True)
def mock_config(tmp_path, monkeypatch):
    # Mock CONFIG_DIR and CONFIG_FILE to use a temporary directory
    config_dir = tmp_path / ".config" / "raindrip"
    config_file = config_dir / "config.json"
    
    monkeypatch.setattr("raindrip.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("raindrip.config.CONFIG_FILE", config_file)
    
    # Save a mock token
    save_config(Config(token="test-token"))

def test_whoami_json():
    mock_user = {"fullName": "Test User", "_id": 12345}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").mock(
            return_value=Response(200, json={"user": mock_user})
        )
        
        result = runner.invoke(app, ["--format", "json", "whoami"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["fullName"] == "Test User"

def test_context_toon():
    # We need to mock multiple calls for context
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").mock(
            return_value=Response(200, json={"user": {"fullName": "Test User", "_id": 1}})
        )
        respx_mock.get("/user/stats").mock(
            return_value=Response(200, json={"items": [{"_id": 0, "count": 100}]})
        )
        respx_mock.get("/raindrops/0").mock(
            return_value=Response(200, json={"items": [{"_id": 123, "title": "Recent", "link": "http://test.com"}]})
        )
        respx_mock.get("/collections/all").mock(
            return_value=Response(200, json={"items": [{"_id": 456, "title": "Col", "count": 5}]})
        )
        
        result = runner.invoke(app, ["--format", "toon", "context"])
        if result.exit_code != 0:
            print(result.output)
        assert result.exit_code == 0
        # TOON output is tabular, check for keywords
        assert "Test User" in result.stdout
        assert "total_bookmarks" in result.stdout
        assert "Recent" in result.stdout

def test_search_json():
    mock_results = {
        "items": [
            {"_id": 1, "title": "Result 1", "link": "http://r1.com", "tags": ["t1"]},
        ]
    }
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrops/0").mock(
            return_value=Response(200, json=mock_results)
        )
        
        result = runner.invoke(app, ["--format", "json", "search", "test"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["items"][0]["title"] == "Result 1"

def test_search_pretty():
    mock_results = {
        "items": [
            {"_id": 1, "title": "Result 1", "link": "http://r1.com", "tags": ["t1"]},
            {"_id": 2, "title": "Result 2", "link": "http://r2.com", "tags": []}
        ]
    }
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrops/0").mock(
            return_value=Response(200, json=mock_results)
        )
        
        result = runner.invoke(app, ["search", "test", "--pretty"])
        assert result.exit_code == 0
        assert "Result 1" in result.stdout
        assert "Result 2" in result.stdout
        assert "ID" in result.stdout # Table header

def test_schema():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "schemas" in data
    assert "usage_examples" in data

def test_structure_json():
    mock_collections = {"items": [{"_id": 1, "title": "Col 1", "count": 10}]}
    mock_tags = {"items": [{"_id": "tag1", "count": 5}]}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/all").mock(return_value=Response(200, json=mock_collections))
        respx_mock.get("/tags").mock(return_value=Response(200, json=mock_tags))
        
        result = runner.invoke(app, ["--format", "json", "structure"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["collections"]) == 1
        assert data["collections"][0]["title"] == "Col 1"
        assert "tag1" in data["tags"]

def test_add_bookmark():
    mock_item = {"item": {"_id": 123, "title": "Added", "link": "http://added.com"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.post("/raindrop").mock(return_value=Response(200, json=mock_item))
        
        result = runner.invoke(app, ["--format", "json", "add", "http://added.com", "--title", "Added"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 123

def test_delete_bookmark():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/raindrop/123").mock(return_value=Response(200, json={"result": True}))
        
        result = runner.invoke(app, ["--format", "json", "delete", "123"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True

def test_sort_bookmark():
    mock_item = {"item": {"_id": 123, "title": "Python coding", "link": "http://py.com"}}
    mock_collections = {
        "items": [
            {"_id": 1, "title": "Python", "count": 10},
            {"_id": 2, "title": "Cooking", "count": 5}
        ]
    }
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/123").mock(return_value=Response(200, json=mock_item))
        respx_mock.get("/collections/all").mock(return_value=Response(200, json=mock_collections))
        
        result = runner.invoke(app, ["--format", "json", "sort", "123"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["bookmark"]["id"] == 123
        assert len(data["suggested_collections"]) > 0
        assert data["suggested_collections"][0]["title"] == "Python"

def test_cli_error_hint():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").mock(
            return_value=Response(401, json={"errorMessage": "Unauthorized"})
        )
        
        result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "Authentication failed" in data["hint"]

def test_collection_create():
    mock_item = {"item": {"_id": 123, "title": "New Col"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.post("/collection").mock(return_value=Response(200, json=mock_item))
        result = runner.invoke(app, ["--format", "json", "collection", "create", "New Col"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["id"] == 123

def test_collection_update():
    mock_item = {"item": {"_id": 123, "title": "Updated"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/collection/123").mock(return_value=Response(200, json=mock_item))
        result = runner.invoke(app, ["--format", "json", "collection", "update", "123", '{"title": "Updated"}'])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["title"] == "Updated"

def test_collection_delete():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/collection/123").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "collection", "delete", "123"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_collection_get():
    mock_item = {"item": {"_id": 123, "title": "Get Col"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collection/123").mock(return_value=Response(200, json=mock_item))
        result = runner.invoke(app, ["--format", "json", "collection", "get", "123"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["id"] == 123

def test_tag_rename():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/tags/0").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "tag", "rename", "old", "new"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_batch_update():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/raindrops/0").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "batch", "update", "--ids", "1,2", '{"title": "Batch"}'])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_batch_delete():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/raindrops/0").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "batch", "delete", "--ids", "1,2"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_logout(monkeypatch, tmp_path):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("raindrip.config.CONFIG_FILE", config_file)
    save_config(Config(token="test"))
    assert config_file.exists()
    
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert not config_file.exists()

def test_get_raindrop():
    mock_item = {"item": {"_id": 123, "title": "Single", "link": "http://one.com"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/123").mock(return_value=Response(200, json=mock_item))
        result = runner.invoke(app, ["--format", "json", "get", "123"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["id"] == 123

def test_suggest_raindrop():
    mock_data = {"item": {"tags": ["suggested"]}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/123/suggest").mock(return_value=Response(200, json=mock_data))
        result = runner.invoke(app, ["--format", "json", "suggest", "123"])
        assert result.exit_code == 0
        assert "suggested" in json.loads(result.stdout)["tags"]

def test_wayback():
    snapshot = "http://archive.org/snapshot"
    mock_resp = {"archived_snapshots": {"closest": {"url": snapshot, "available": True}}}
    with respx.mock() as respx_mock:
        respx_mock.get("https://archive.org/wayback/available").mock(return_value=Response(200, json=mock_resp))
        result = runner.invoke(app, ["--format", "json", "wayback", "http://google.com"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["snapshot"] == snapshot

def test_patch_raindrop():
    mock_item = {"item": {"_id": 123, "title": "Patched", "link": "http://one.com"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/raindrop/123").mock(return_value=Response(200, json=mock_item))
        result = runner.invoke(app, ["--format", "json", "patch", "123", '{"title": "Patched"}'])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["title"] == "Patched"

def test_collection_clean():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/collections/clean").mock(return_value=Response(200, json={"count": 5}))
        result = runner.invoke(app, ["--format", "json", "collection", "clean"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["removed_count"] == 5

def test_collection_empty_trash():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/collection/-99").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "collection", "empty-trash"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_collection_reorder():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/collections").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "collection", "reorder", "title"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_collection_expand_all():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/collections").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "collection", "expand-all", "True"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_collection_merge():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/collections/merge").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "collection", "merge", "1,2", "3"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_collection_delete_multiple():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/collections").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "collection", "delete-multiple", "1,2"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_tag_delete():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.delete("/tags/0").mock(return_value=Response(200, json={"result": True}))
        result = runner.invoke(app, ["--format", "json", "tag", "delete", "tag1"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["success"] is True

def test_collection_set_icon(tmp_path):
    icon_resp = b"fake-icon-content"
    mock_item = {"item": {"_id": 123, "title": "Updated Icon"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/covers/robot").mock(return_value=Response(200, json={"items": [{"icons": [{"png": "http://icon.com/1.png"}]}]}))
        # Mock external download
        respx_mock.get("http://icon.com/1.png").mock(return_value=Response(200, content=icon_resp))
        respx_mock.put("/collection/123/cover").mock(return_value=Response(200, json=mock_item))
        
        result = runner.invoke(app, ["--format", "json", "collection", "set-icon", "123", "robot"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["id"] == 123

def test_collection_cover_local(tmp_path):
    cover_file = tmp_path / "cover.png"
    cover_file.write_bytes(b"fake-png")
    mock_item = {"item": {"_id": 123, "title": "Updated Cover"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.put("/collection/123/cover").mock(return_value=Response(200, json=mock_item))
        
        result = runner.invoke(app, ["--format", "json", "collection", "cover", "123", str(cover_file)])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["id"] == 123

def test_login():
    mock_user = {"fullName": "Login User", "_id": 1}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").mock(return_value=Response(200, json={"user": mock_user}))
        result = runner.invoke(app, ["login"], input="new-token\n")
        assert result.exit_code == 0
        assert "Success" in result.stdout

def test_collection_cover_url(tmp_path):
    mock_item = {"item": {"_id": 123, "title": "Updated Cover"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("http://example.com/icon.png").mock(return_value=Response(200, content=b"png-data"))
        respx_mock.put("/collection/123/cover").mock(return_value=Response(200, json=mock_item))
        
        result = runner.invoke(app, ["--format", "json", "collection", "cover", "123", "http://example.com/icon.png"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["id"] == 123

def test_collection_set_icon_no_results():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/covers/nothing").mock(return_value=Response(200, json={"items": []}))
        result = runner.invoke(app, ["collection", "set-icon", "123", "nothing"])
        assert result.exit_code == 0
        assert "No icons found" in result.stdout

def test_invalid_json_input():
    result = runner.invoke(app, ["patch", "123", "{invalid-json"])
    assert result.exit_code == 1
    assert "Invalid JSON" in result.stdout

def test_batch_delete_invalid_ids():
    result = runner.invoke(app, ["batch", "delete", "--ids", "not-an-int"])
    assert result.exit_code == 1
    assert "Invalid IDs" in result.stdout

def test_output_data_list_models_json():
    # To cover OutputFormat.json with a list of models
    mock_collections = {"items": [{"_id": 1, "title": "Col 1", "count": 10}]}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/all").mock(return_value=Response(200, json=mock_collections))
        respx_mock.get("/tags").mock(return_value=Response(200, json={"items": []}))
        
        result = runner.invoke(app, ["--format", "json", "structure"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["collections"]) == 1
        assert "id" in data["collections"][0]

def test_output_data_list_models_json():

    # This triggers the dumped = [item.model_dump() ... else item] line
    # when data is a list of strings
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/collections/all").mock(return_value=Response(200, json={"items": []}))
        respx_mock.get("/tags").mock(return_value=Response(200, json={"items": [{"_id": "t1"}]}))
        result = runner.invoke(app, ["--format", "json", "structure"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["tags"] == ["t1"]

def test_output_data_single_model_json():
    # To cover line 51: dumped = data.model_dump()
    # We can use the 'get' command which returns a single Raindrop model
    mock_item = {"item": {"_id": 123, "title": "Single", "link": "http://one.com"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/123").mock(return_value=Response(200, json=mock_item))
        result = runner.invoke(app, ["--format", "json", "get", "123"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 123
        assert "title" in data

def test_cli_404_hint():
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/999").mock(
            return_value=Response(404, json={"errorMessage": "Not Found"})
        )
        
        result = runner.invoke(app, ["get", "999"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert "requested resource was not found" in data["hint"]

def test_unexpected_error():
    # Force an exception by mocking something internal
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/user").side_effect = Exception("Boom")
        result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 1
        assert "Unexpected error" in result.stdout

def test_json_output_single_model():
    mock_item = {"item": {"_id": 123, "title": "Single", "link": "http://one.com"}}
    with respx.mock(base_url=BASE_URL) as respx_mock:
        respx_mock.get("/raindrop/123").mock(return_value=Response(200, json=mock_item))
        result = runner.invoke(app, ["--format", "json", "get", "123"])
        assert result.exit_code == 0
        # result.stdout should be valid JSON
        data = json.loads(result.stdout)
        assert data["id"] == 123

def test_dry_run():
    # Dry run should not make real requests for POST/PUT/DELETE
    # But it still needs to load config
    result = runner.invoke(app, ["--dry-run", "delete", "123"])
    assert result.exit_code == 0
    assert "success" in result.stdout

def test_no_config(tmp_path, monkeypatch):
    # Use a fresh empty directory
    config_dir = tmp_path / "empty"
    monkeypatch.setattr("raindrip.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("raindrip.config.CONFIG_FILE", config_dir / "none.json")
    
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 1
    assert "Not logged in" in result.stdout

def test_malformed_config(tmp_path, monkeypatch):
    config_dir = tmp_path / "malformed"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text("{malformed")
    monkeypatch.setattr("raindrip.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("raindrip.config.CONFIG_FILE", config_file)
    
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 1
    assert "Not logged in" in result.stdout
