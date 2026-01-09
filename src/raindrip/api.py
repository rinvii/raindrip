import httpx
import asyncio
import json
from typing import List, Optional, Any, Dict
from rich import print as rprint
from .models import (
    Raindrop,
    Collection,
    RaindropUpdate,
    CollectionCreate,
    CollectionUpdate,
)


class RaindropError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: int = 500, hint: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.hint = hint


class RateLimitError(RaindropError):
    """Raised when rate limits are exhausted."""

    def __init__(self, retry_after: int):
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s", 429)


class ServerError(RaindropError):
    """Raised when Raindrop.io is down (5xx)."""

    def __init__(self, message: str):
        super().__init__(message, 502)


class RaindropAPI:
    BASE_URL = "https://api.raindrop.io/rest/v1"
    WAYBACK_URL = "https://archive.org/wayback/available"
    MAX_RETRIES = 3

    def __init__(self, token: str, dry_run: bool = False):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=30.0)
        self.dry_run = dry_run

    async def close(self):
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """
        Robust request handler with Rate Limit support, Error handling, and Dry Run.
        """
        if self.dry_run and method in ["POST", "PUT", "DELETE"]:
            # Format logs for Dry Run
            payload = kwargs.get("json", kwargs.get("params", {}))
            rprint(f"[bold yellow][DRY RUN][/bold yellow] {method} {path}")
            if payload:
                # Basic sanitation: never log tokens if they happen to be in payload
                filtered_payload = {k: v for k, v in payload.items() if "token" not in k.lower()}
                rprint(f"[dim]Payload: {json.dumps(filtered_payload, indent=2)}[/dim]")
            
            if method == "DELETE":
                return {"result": True}
            return {"result": True, "item": {"_id": 0, "title": "Dry Run Item", "link": "http://dryrun.com"}, "items": []}

        retries = self.MAX_RETRIES
        while retries > 0:
            try:
                response = await self.client.request(
                    method, f"{self.BASE_URL}{path}", headers=self.headers, **kwargs
                )

                if response.status_code == 429:
                    retries -= 1
                    retry_after = int(response.headers.get("Retry-After", 10))
                    rprint(f"[yellow]Rate limited. Retrying in {retry_after}s... ({retries} retries left)[/yellow]")
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code >= 500:
                    retries -= 1
                    if retries == 0:
                        raise ServerError(
                            f"Raindrop.io Server Error: {response.status_code}"
                        )
                    await asyncio.sleep(2)
                    continue

                response.raise_for_status()
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    raise RaindropError(f"Invalid JSON response from API: {str(e)}", 502) from e

            except httpx.HTTPStatusError as e:
                # 4xx errors: Include the API's error message if available
                error_detail = e.response.text
                try:
                    error_json = e.response.json()
                    error_detail = error_json.get("errorMessage", error_detail)
                except Exception:
                    pass
                
                raise RaindropError(
                    f"API Error {e.response.status_code}: {error_detail}",
                    status_code=e.response.status_code,
                ) from e
            except httpx.RequestError as e:
                raise RaindropError(f"Network Error: {str(e)}", status_code=503) from e
        
        raise RaindropError("Maximum retries exceeded", 504)

    async def check_wayback(self, url: str) -> Optional[str]:
        """
        Check if a URL is available in the Wayback Machine.
        Returns the snapshot URL if found, None otherwise.
        """
        try:
            response = await self.client.get(self.WAYBACK_URL, params={"url": url})
            if response.status_code == 200:
                data = response.json()
                snapshots = data.get("archived_snapshots", {})
                closest = snapshots.get("closest", {})
                return closest.get("url")
        except Exception:
            pass
        return None

    async def get_user(self) -> Dict[str, Any]:
        data = await self._request("GET", "/user")
        return data.get("user", {})

    async def get_stats(self) -> List[Dict[str, Any]]:
        """Get account statistics (counts of raindrops, collections, tags)."""
        data = await self._request("GET", "/user/stats")
        return data.get("items", [])

    async def get_collections(self) -> List[Collection]:
        data = await self._request("GET", "/collections/all")
        return [Collection.model_validate(item) for item in data.get("items", [])]

    async def get_root_collections(self) -> List[Collection]:
        data = await self._request("GET", "/collections")
        return [Collection.model_validate(item) for item in data.get("items", [])]

    async def get_child_collections(self) -> List[Collection]:
        data = await self._request("GET", "/collections/childrens")
        return [Collection.model_validate(item) for item in data.get("items", [])]

    async def get_collection(self, collection_id: int) -> Collection:
        data = await self._request("GET", f"/collection/{collection_id}")
        return Collection.model_validate(data.get("item", {}))

    async def create_collection(self, collection: CollectionCreate) -> Collection:
        data = await self._request(
            "POST", "/collection", json=collection.model_dump(exclude_none=True)
        )
        return Collection.model_validate(data.get("item", {}))

    async def update_collection(
        self, collection_id: int, update: CollectionUpdate
    ) -> Collection:
        data = await self._request(
            "PUT",
            f"/collection/{collection_id}",
            json=update.model_dump(exclude_none=True),
        )
        return Collection.model_validate(data.get("item", {}))

    async def delete_collection(self, collection_id: int) -> bool:
        data = await self._request("DELETE", f"/collection/{collection_id}")
        return data.get("result", False)

    async def delete_collections(self, ids: List[int]) -> bool:
        data = await self._request("DELETE", "/collections", json={"ids": ids})
        return data.get("result", True) # API returns empty body on success for this one sometimes

    async def reorder_collections(self, sort: str) -> bool:
        data = await self._request("PUT", "/collections", json={"sort": sort})
        return data.get("result", False)

    async def expand_all_collections(self, expanded: bool) -> bool:
        data = await self._request("PUT", "/collections", json={"expanded": expanded})
        return data.get("result", False)

    async def merge_collections(self, ids: List[int], target_id: int) -> bool:
        data = await self._request(
            "PUT", "/collections/merge", json={"ids": ids, "to": target_id}
        )
        return data.get("result", True)

    async def clean_empty_collections(self) -> int:
        data = await self._request("PUT", "/collections/clean")
        return data.get("count", 0)

    async def upload_collection_cover(self, collection_id: int, file_path: str) -> Collection:
        """Upload a cover image for a collection."""
        if self.dry_run:
            rprint(f"[bold yellow][DRY RUN][/bold yellow] PUT /collection/{collection_id}/cover")
            rprint(f"[dim]File: {file_path}[/dim]")
            return Collection.model_validate({"_id": collection_id, "title": "Dry Run Icon"})

        with open(file_path, "rb") as f:
            files = {"cover": (file_path, f, "image/png")}
            # We use the client directly to handle multipart upload which _request doesn't support easily
            response = await self.client.put(
                f"{self.BASE_URL}/collection/{collection_id}/cover",
                headers={"Authorization": self.headers["Authorization"]},
                files=files
            )
            response.raise_for_status()
            data = response.json()
            return Collection.model_validate(data.get("item", {}))

    async def search_cover(self, query: str) -> List[str]:
        """Search for cover icons by query."""
        data = await self._request("GET", f"/collections/covers/{query}")
        # Flatten the results to just a list of PNG URLs
        icons = []
        for group in data.get("items", []):
            for icon in group.get("icons", []):
                if "png" in icon:
                    icons.append(icon["png"])
        return icons

    async def empty_trash(self) -> bool:
        data = await self._request("DELETE", "/collection/-99")
        return data.get("result", False)

    async def get_tags(self) -> List[str]:
        data = await self._request("GET", "/tags")
        return [item["_id"] for item in data.get("items", [])]

    async def delete_tags(self, tags: List[str], collection_id: int = 0) -> bool:
        """Delete tags globally (0) or from a specific collection."""
        data = await self._request(
            "DELETE", f"/tags/{collection_id}", json={"tags": tags}
        )
        return data.get("result", False)

    async def rename_tag(
        self, old_name: str, new_name: str, collection_id: int = 0
    ) -> bool:
        """Rename a tag (merges if new_name exists)."""
        data = await self._request(
            "PUT",
            f"/tags/{collection_id}",
            json={"replace": new_name, "tags": [old_name]},
        )
        return data.get("result", False)

    async def search(self, query: str = "", collection_id: int = 0) -> List[Raindrop]:
        page = 0
        all_items = []

        while True:
            params = {"search": query, "page": page, "perpage": 50}
            data = await self._request(
                "GET", f"/raindrops/{collection_id}", params=params
            )
            items = data.get("items", [])

            if not items:
                break

            all_items.extend([Raindrop.model_validate(item) for item in items])

            if len(items) < 50:
                break

            page += 1

        return all_items

    async def get_raindrop(self, raindrop_id: int) -> Raindrop:
        data = await self._request("GET", f"/raindrop/{raindrop_id}")
        return Raindrop.model_validate(data.get("item", {}))

    async def add_raindrop(
        self,
        link: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        collection_id: Optional[int] = None,
    ) -> Raindrop:
        payload = {"link": link}
        if title:
            payload["title"] = title
        if tags:
            payload["tags"] = tags
        if collection_id is not None:
            payload["collectionId"] = collection_id

        data = await self._request("POST", "/raindrop", json=payload)
        return Raindrop.model_validate(data.get("item", {}))

    async def update_raindrop(
        self, raindrop_id: int, update: RaindropUpdate
    ) -> Raindrop:
        data = await self._request(
            "PUT", f"/raindrop/{raindrop_id}", json=update.model_dump(exclude_none=True)
        )
        return Raindrop.model_validate(data.get("item", {}))

    async def delete_raindrop(self, raindrop_id: int) -> bool:
        data = await self._request("DELETE", f"/raindrop/{raindrop_id}")
        return data.get("result", False)

    async def batch_update_raindrops(
        self, collection_id: int, ids: List[int], update: RaindropUpdate
    ) -> bool:
        """Batch update raindrops in a collection."""
        payload = update.model_dump(exclude_none=True)
        payload["ids"] = ids
        data = await self._request("PUT", f"/raindrops/{collection_id}", json=payload)
        return data.get("result", False)

    async def batch_delete_raindrops(self, collection_id: int, ids: List[int]) -> bool:
        """Batch delete raindrops in a collection."""
        data = await self._request(
            "DELETE", f"/raindrops/{collection_id}", json={"ids": ids}
        )
        return data.get("result", False)

    async def get_suggestions(self, raindrop_id: int) -> Dict[str, List[str]]:
        data = await self._request("GET", f"/raindrop/{raindrop_id}/suggest")
        return data.get("item", {})
