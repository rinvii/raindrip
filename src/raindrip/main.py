import asyncio
import json
import os
import httpx
import toon_format as toon
from enum import Enum
from typing import List, Optional, Any
import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from .config import load_config, save_config, delete_config, Config
from .api import RaindropAPI, RaindropError
from .models import RaindropUpdate, Raindrop, CollectionCreate, CollectionUpdate

app = typer.Typer(help="raindrip: A standalone, AI-friendly CLI for Raindrop.io")
collection_app = typer.Typer(help="Manage collections")
tag_app = typer.Typer(help="Manage tags")
batch_app = typer.Typer(help="Batch operations on bookmarks")
console = Console()

class OutputFormat(str, Enum):
    json = "json"
    toon = "toon"

class State:
    dry_run: bool = False
    output_format: OutputFormat = OutputFormat.toon

state = State()

@app.callback()
def main(
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions instead of making real API requests."),
    format: OutputFormat = typer.Option(OutputFormat.toon, "--format", "-f", help="Output format: toon (default, highest token efficiency) or json.")
):
    """
    raindrip: AI-native CLI for Raindrop.io
    """
    state.dry_run = dry_run
    state.output_format = format

def output_data(data: Any):
    """Helper to output data in the selected format."""
    # Ensure data is JSON-serializable (dicts/lists) for both formats
    if isinstance(data, list):
        dumped = [item.model_dump() if hasattr(item, "model_dump") else item for item in data]
    elif hasattr(data, "model_dump"):
        dumped = data.model_dump()
    else:
        dumped = data

    if state.output_format == OutputFormat.toon:
        print(toon.encode(dumped))
    else:
        print(json.dumps(dumped, indent=2))

def get_authenticated_api() -> RaindropAPI:
    config = load_config()
    if not config.token:
        rprint("[bold red]Error:[/bold red] Not logged in. Run `raindrip login` first.")
        raise typer.Exit(code=1)
    return RaindropAPI(config.token, dry_run=state.dry_run)

async def cleanup_api(api: RaindropAPI):
    await api.close()

# Decorator to handle errors gracefully and force JSON output for errors
def handle_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            await func(*args, **kwargs)
        except json.JSONDecodeError:
            print(json.dumps({
                "error": "Invalid JSON input provided to command.",
                "status": 400,
                "hint": "Ensure your JSON data is valid and properly escaped for the shell."
            }))
            raise typer.Exit(code=1)
        except RaindropError as e:
            hint = e.hint
            if not hint:
                if e.status_code == 404:
                    hint = "The requested resource was not found. Verify the ID is correct."
                elif e.status_code == 401:
                    hint = "Authentication failed. Try running 'raindrip login' again."
            
            print(json.dumps({
                "error": str(e), 
                "status": e.status_code,
                "hint": hint
            }, indent=2 if not getattr(wrapper, "compact", False) else None))
            raise typer.Exit(code=1)
        except Exception as e:
            print(json.dumps({
                "error": f"Unexpected error: {str(e)}", 
                "status": 500,
                "hint": "Check the CLI logs or report this issue."
            }))
            raise typer.Exit(code=1)
    return wrapper

@app.command()
def login(token: str = typer.Option(..., prompt="Enter your Raindrop.io API Token", hide_input=True)):
    """
    Login with your Raindrop.io API token (verifies before saving).
    
    Example: raindrip login
    """
    
    @handle_errors
    async def verify():
        api = RaindropAPI(token)
        try:
            rprint("Verifying token...")
            user = await api.get_user()
            save_config(Config(token=token))
            rprint(f"[bold green]Success![/bold green] Logged in as [bold]{user.get('fullName')}[/bold].")
        finally:
            await api.close()
            
    asyncio.run(verify())

@app.command()
def logout():
    """
    Remove your stored credentials.
    
    Example: raindrip logout
    """
    delete_config()
    rprint("[bold yellow]Logged out.[/bold yellow] Credentials removed.")

@app.command()
def whoami():
    """
    Show current user details.
    
    Example: raindrip whoami
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            user = await api.get_user()
            output_data(user)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def context():
    """
    Show high-level account context (User, Stats, Recent Activity).
    
    Example: raindrip context
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            # Parallel fetch for speed
            user, stats, recent, collections = await asyncio.gather(
                api.get_user(),
                api.get_stats(),
                api.search(collection_id=0), # Default page 0 is recent items
                api.get_collections()
            )
            
            # Simplified Context Output
            context_data = {
                "user": [{"id": user.get("_id"), "name": user.get("fullName")}],
                "stats": [{
                    "total_bookmarks": next((s["count"] for s in stats if s["_id"] == 0), 0),
                    "total_collections": len(collections),
                }],
                "structure": {
                    "root_collections": [
                        {"id": c.id, "title": c.title, "count": c.count} 
                        for c in collections if not getattr(c, "parent", None) # Top level only
                    ]
                },
                "recent_activity": [
                    {"id": r.id, "title": r.title, "created": r.id} # ID is roughly chronological
                    for r in recent[:5]
                ]
            }
            output_data(context_data)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def structure():
    """
    Show collections and tags.
    
    Example: raindrip structure
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            collections, tags = await asyncio.gather(
                api.get_collections(),
                api.get_tags()
            )
            output_data({
                "collections": [
                    {
                        "id": c.id, 
                        "title": c.title, 
                        "count": c.count, 
                        "parent_id": c.parent.get("$id") if c.parent else None,
                        "last_update": c.lastUpdate
                    } for c in collections
                ],
                "tags": tags
            })
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def schema():
    """
    Dump the JSON Schemas and usage examples (For AI context).
    
    Example: raindrip schema
    """
    print(json.dumps({
        "schemas": {
            "Raindrop": Raindrop.model_json_schema(),
            "RaindropUpdate": RaindropUpdate.model_json_schema(),
            "CollectionCreate": CollectionCreate.model_json_schema(),
            "CollectionUpdate": CollectionUpdate.model_json_schema(),
        },
        "usage_examples": {
            "patch_update_title_tags": "raindrip patch <id> '{\"title\": \"New Title\", \"tags\": [\"ai\", \"cli\"]}'",
            "move_single_bookmark": "raindrip patch <id> '{\"collectionId\": <target_col_id>}'",
            "move_batch_bookmarks": "raindrip batch update --ids 1,2 --collection <source_col_id> '{\"collection\": {\"$id\": <target_col_id>}}'",
            "create_collection": "raindrip collection create \"Research\" --public",
            "set_collection_icon_search": "raindrip collection set-icon <id> \"robot\"",
            "set_collection_icon_url": "raindrip collection cover <id> \"https://example.com/icon.png\"",
            "complex_query": "raindrip search \"python tag:important\" --pretty"
        }
    }, indent=2))

@app.command()
def search(
    query: str = typer.Argument("", help="Search query"), 
    collection: int = 0,
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Display results in a formatted table for humans."),
    format: Optional[OutputFormat] = typer.Option(None, "--format", "-f", help="Output format: toon or json."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions instead of making real API requests.")
):
    """
    Search for bookmarks (paginated).
    
    Examples: 
    raindrip search "python"
    raindrip search "tag:important" --pretty
    """
    if format:
        state.output_format = format
    if dry_run:
        state.dry_run = True
        
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            results = await api.search(query, collection)
            if pretty:
                # Rich Table for Humans
                table = Table(title=f"Search Results: {query}" if query else "Recent Bookmarks")
                table.add_column("ID", style="cyan")
                table.add_column("Title", style="white")
                table.add_column("Tags", style="green")
                table.add_column("Link", style="blue")
                
                for r in results:
                    table.add_row(
                        str(r.id),
                        r.title[:50] + ("..." if len(r.title) > 50 else ""),
                        ", ".join(r.tags),
                        r.link[:50] + ("..." if len(r.link) > 50 else "")
                    )
                console.print(table)
                rprint(f"\n[dim]Total results: {len(results)}[/dim]")
            else:
                # Flatten tags and wrap in object for TOON efficiency/compatibility
                results_data = {
                    "items": [
                        {
                            "id": r.id, 
                            "title": r.title, 
                            "link": r.link, 
                            "tags": ",".join(r.tags) if r.tags else "",
                            "type": r.type or "link",
                            "created": r.created
                        } for r in results
                    ]
                }
                output_data(results_data)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def get(raindrop_id: int):
    """
    Get full details for a specific bookmark.
    
    Example: raindrip get 123456
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            result = await api.get_raindrop(raindrop_id)
            output_data(result)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def suggest(raindrop_id: int):
    """
    Get tag/collection suggestions for a bookmark.
    
    Example: raindrip suggest 123456
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            suggestions = await api.get_suggestions(raindrop_id)
            output_data(suggestions)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def wayback(url: str):
    """
    Check if a URL is available in the Wayback Machine.
    
    Example: raindrip wayback "https://google.com"
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            snapshot = await api.check_wayback(url)
            output_data({"url": url, "snapshot": snapshot})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def add(url: str, title: Optional[str] = None, tags: Optional[str] = None, collection: Optional[int] = None):
    """
    Add a new bookmark.
    
    Example: raindrip add "https://example.com" --title "Example" --tags "tag1,tag2"
    """
    api = get_authenticated_api()
    tag_list = tags.split(",") if tags else None
    @handle_errors
    async def run():
        try:
            result = await api.add_raindrop(url, title, tag_list, collection)
            output_data(result)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def patch(raindrop_id: int, data: str):
    """
    Update a bookmark with a JSON patch.
    
    Example: raindrip patch 123456 '{"title": "New Title", "tags": ["updated"]}'
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        patch_data = json.loads(data)
        update = RaindropUpdate.model_validate(patch_data)
        try:
            result = await api.update_raindrop(raindrop_id, update)
            output_data(result)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def delete(raindrop_id: int):
    """
    Delete a bookmark.
    
    Example: raindrip delete 123456
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            success = await api.delete_raindrop(raindrop_id)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@app.command()
def sort(raindrop_id: int):
    """
    Suggest the best collection for a bookmark based on its title.
    
    Example: raindrip sort 123456
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            bookmark = await api.get_raindrop(raindrop_id)
            collections = await api.get_collections()
            
            # Simple keyword matching logic
            suggestions = []
            title_lower = bookmark.title.lower()
            
            for col in collections:
                col_title = col.title.lower()
                # Score based on keyword overlap
                if col_title in title_lower or any(word in title_lower for word in col_title.split()):
                    suggestions.append({
                        "id": col.id,
                        "title": col.title,
                        "match_reason": f"Matches keyword '{col.title}'"
                    })
            
            output_data({
                "bookmark": {"id": bookmark.id, "title": bookmark.title},
                "suggested_collections": suggestions[:3] # Top 3
            })
        finally:
            await cleanup_api(api)
    asyncio.run(run())

# Collection Commands
@collection_app.command("create")
def collection_create(
    title: str,
    parent: Optional[int] = typer.Option(None, help="Parent collection ID"),
    public: Optional[bool] = typer.Option(None, help="Make collection public"),
    view: Optional[str] = typer.Option(None, help="View style (list, simple, grid, masonry)"),
    format: Optional[OutputFormat] = typer.Option(None, "--format", "-f", help="Output format: toon or json."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions instead of making real API requests.")
):
    """
    Create a new collection.
    
    Example: raindrip collection create "Research" --public
    """
    if format:
        state.output_format = format
    if dry_run:
        state.dry_run = True
        
    api = get_authenticated_api()
    parent_dict = {"$id": parent} if parent is not None else None
    
    new_collection = CollectionCreate(
        title=title,
        parent=parent_dict,
        public=public,
        view=view
    )

    @handle_errors
    async def run():
        try:
            result = await api.create_collection(new_collection)
            output_data(result)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("update")
def collection_update(collection_id: int, data: str):
    """
    Update a collection with a JSON patch.
    
    Example: raindrip collection update 123 '{"title": "New Name"}'
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        patch_data = json.loads(data)
        update = CollectionUpdate.model_validate(patch_data)
        try:
            result = await api.update_collection(collection_id, update)
            output_data(result)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("delete")
def collection_delete(collection_id: int):
    """
    Delete a collection.
    
    Example: raindrip collection delete 123
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            success = await api.delete_collection(collection_id)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("get")
def collection_get(collection_id: int):
    """
    Get details of a specific collection.
    
    Example: raindrip collection get 123
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            result = await api.get_collection(collection_id)
            output_data(result)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("delete-multiple")
def collection_delete_multiple(ids: str = typer.Argument(..., help="Comma-separated list of collection IDs")):
    """
    Delete multiple collections at once.
    
    Example: raindrip collection delete-multiple 123,456
    """
    api = get_authenticated_api()
    id_list = [int(i.strip()) for i in ids.split(",")]
    @handle_errors
    async def run():
        try:
            success = await api.delete_collections(id_list)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("reorder")
def collection_reorder(sort: str = typer.Argument(..., help="Sort order: title, -title, -count")):
    """
    Reorder all collections.
    
    Example: raindrip collection reorder title
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            success = await api.reorder_collections(sort)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("expand-all")
def collection_expand_all(expanded: bool = typer.Argument(..., help="True to expand, False to collapse")):
    """
    Expand or collapse all collections.
    
    Example: raindrip collection expand-all True
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            success = await api.expand_all_collections(expanded)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("merge")
def collection_merge(
    ids: str = typer.Argument(..., help="Comma-separated list of collection IDs to merge"),
    target_id: int = typer.Argument(..., help="Target collection ID")
):
    """
    Merge multiple collections into one.
    
    Example: raindrip collection merge 123,456 789
    """
    api = get_authenticated_api()
    id_list = [int(i.strip()) for i in ids.split(",")]
    @handle_errors
    async def run():
        try:
            success = await api.merge_collections(id_list, target_id)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("cover")
def collection_cover(
    collection_id: int = typer.Argument(..., help="Collection ID"),
    source: str = typer.Argument(..., help="File path or URL of the cover image")
):
    """
    Upload a cover image to a collection.
    
    Example: raindrip collection cover 123 "https://example.com/icon.png"
    """
    api = get_authenticated_api()
    
    @handle_errors
    async def run():
        file_path = source
        is_temp = False
        
        try:
            with console.status("[bold green]Processing cover...") as status:
                # Handle URL
                if source.startswith("http://") or source.startswith("https://"):
                    status.update(f"[bold blue]Downloading cover from {source}...")
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(source)
                        resp.raise_for_status()
                        file_path = "temp_cover.png"
                        with open(file_path, "wb") as f:
                            f.write(resp.content)
                        is_temp = True

                status.update(f"[bold yellow]Uploading cover to collection {collection_id}...")
                result = await api.upload_collection_cover(collection_id, file_path)
                output_data(result)
            
        finally:
            if is_temp and os.path.exists(file_path):
                os.remove(file_path)
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("set-icon")
def collection_set_icon(
    collection_id: int = typer.Argument(..., help="Collection ID"),
    query: str = typer.Argument(..., help="Search query for icon (e.g. 'code', 'art')"),
    format: Optional[OutputFormat] = typer.Option(None, "--format", "-f", help="Output format: toon or json."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions instead of making real API requests.")
):
    """
    Search for and set a collection icon using Raindrop's library.
    
    Example: raindrip collection set-icon 123 "robot"
    """
    if format:
        state.output_format = format
    if dry_run:
        state.dry_run = True
        
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            with console.status(f"[bold green]Searching icons for '{query}'...") as status:
                icons = await api.search_cover(query)
                if not icons:
                    rprint("[red]No icons found.[/red]")
                    return
                
                # Pick the first one (usually best match)
                icon_url = icons[0]
                status.update(f"[bold blue]Found icon, downloading...")
                
                # Download to temp file
                file_path = "temp_icon.png"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(icon_url)
                    resp.raise_for_status()
                    with open(file_path, "wb") as f:
                        f.write(resp.content)
                
                try:
                    status.update(f"[bold yellow]Uploading icon to collection {collection_id}...")
                    result = await api.upload_collection_cover(collection_id, file_path)
                    output_data(result)
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("clean")
def collection_clean():
    """
    Remove all empty collections.
    
    Example: raindrip collection clean
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            count = await api.clean_empty_collections()
            output_data({"removed_count": count})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@collection_app.command("empty-trash")
def collection_empty_trash():
    """
    Empty the trash collection.
    
    Example: raindrip collection empty-trash
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            success = await api.empty_trash()
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

# Tag Commands
@tag_app.command("delete")
def tag_delete(
    tags: List[str] = typer.Argument(..., help="List of tags to delete"),
    collection: int = typer.Option(0, help="Collection ID (0 for global)")
):
    """
    Delete tags from all bookmarks (global) or a specific collection.
    
    Example: raindrip tag delete "old-tag" "useless-tag"
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            success = await api.delete_tags(tags, collection)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@tag_app.command("rename")
def tag_rename(
    old_name: str = typer.Argument(..., help="Current tag name"),
    new_name: str = typer.Argument(..., help="New tag name"),
    collection: int = typer.Option(0, help="Collection ID (0 for global)")
):
    """
    Rename a tag. Merges with existing tag if new name already exists.
    
    Example: raindrip tag rename "work" "career"
    """
    api = get_authenticated_api()
    @handle_errors
    async def run():
        try:
            success = await api.rename_tag(old_name, new_name, collection)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

# Batch Commands
@batch_app.command("update")
def batch_update(
    ids: str = typer.Option(..., help="Comma-separated list of bookmark IDs"),
    data: str = typer.Argument(..., help="JSON patch for updates"),
    collection: int = typer.Option(0, help="Collection ID"),
    format: Optional[OutputFormat] = typer.Option(None, "--format", "-f", help="Output format: toon or json."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Log actions instead of making real API requests.")
):
    """
    Update multiple bookmarks at once.
    
    Example: raindrip batch update --ids 1,2,3 '{"tags": ["research"]}'
    """
    if format:
        state.output_format = format
    if dry_run:
        state.dry_run = True
        
    api = get_authenticated_api()
    @handle_errors
    async def run():
        id_list = [int(i.strip()) for i in ids.split(",")]
        patch_data = json.loads(data)
        update = RaindropUpdate.model_validate(patch_data)
        try:
            success = await api.batch_update_raindrops(collection, id_list, update)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

@batch_app.command("delete")
def batch_delete(
    ids: str = typer.Option(..., help="Comma-separated list of bookmark IDs"),
    collection: int = typer.Option(0, help="Collection ID (use -99 for permanent delete)")
):
    """
    Delete multiple bookmarks at once.
    
    Example: raindrip batch delete --ids 1,2,3
    """
    api = get_authenticated_api()
    try:
        id_list = [int(i.strip()) for i in ids.split(",")]
    except Exception as e:
        rprint(f"[bold red]Error:[/bold red] Invalid IDs: {e}")
        raise typer.Exit(code=1)

    @handle_errors
    async def run():
        try:
            success = await api.batch_delete_raindrops(collection, id_list)
            output_data({"success": success})
        finally:
            await cleanup_api(api)
    asyncio.run(run())

app.add_typer(collection_app, name="collection")
app.add_typer(tag_app, name="tag")
app.add_typer(batch_app, name="batch")

if __name__ == "__main__":
    app()
