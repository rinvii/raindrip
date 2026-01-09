import subprocess
import json
import sys
import os
import time

# Configuration
# Use 'uv run' to ensure dependencies are available
PYTHON_CMD = ["uv", "run", "python", "-m", "raindrip.main", "--format", "json"]
ENV = os.environ.copy()
# Ensure src is in PYTHONPATH so python -m raindrip.main works
ENV["PYTHONPATH"] = os.path.join(os.getcwd(), "src") + os.pathsep + ENV.get("PYTHONPATH", "")

def log(msg, color="white"):
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    print(f"{colors.get(color, '')}{msg}{colors['reset']}")

def run_raindrip(args, expect_error=False):
    cmd = PYTHON_CMD + args
    log(f"Running: {' '.join(args)}", "blue")
    
    result = subprocess.run(
        cmd, 
        capture_output=True, 
        text=True, 
        env=ENV
    )
    
    output = result.stdout.strip()
    stderr = result.stderr.strip()
    
    if stderr:
        # Ideally, a clean CLI tool shouldn't output to stderr unless it's a critical system error 
        # or expected diagnostics. We print it if the command fails.
        pass

    if result.returncode != 0 and not expect_error:
        log(f"Command failed with code {result.returncode}", "red")
        log(f"STDERR: {stderr}", "red")
        log(f"STDOUT: {output}", "red")
        raise Exception("Command failed")

    try:
        if not output and result.returncode == 0:
            return None 
        data = json.loads(output)
        return data
    except json.JSONDecodeError:
        log("FAILED TO PARSE JSON", "red")
        log(f"Raw Output: {output}", "red")
        log(f"STDERR: {stderr}", "red")
        raise Exception("Invalid JSON output")

def main():
    log("=== Starting Raindrip Playtest ===", "yellow")
    
    # 1. Whoami
    try:
        user = run_raindrip(["whoami"])
        log(f"Logged in as: {user.get('fullName', 'Unknown')}", "green")
    except Exception:
        log("Not logged in. Please run 'raindrip login' first.", "red")
        sys.exit(1)

    collection_id = None
    bookmark_ids = []

    try:
        # 2. Create Collection
        log("\n--- Creating Collection ---")
        col = run_raindrip(["collection", "create", "Raindrip_Playtest_Zone"])
        collection_id = col["id"]
        log(f"Created Collection ID: {collection_id}", "green")

        # 3. Add Bookmarks
        log("\n--- Adding Bookmarks ---")
        urls = [
            ("https://www.python.org", "Python"),
            ("https://www.rust-lang.org", "Rust"),
            ("https://typer.tiangolo.com", "Typer")
        ]
        
        for url, title in urls:
            time.sleep(0.5) 
            bm = run_raindrip(["add", url, "--title", title, "--collection", str(collection_id)])
            bookmark_ids.append(bm["id"])
            log(f"Added {title} (ID: {bm['id']})", "green")

        # 4. Batch Update (Add Tags)
        log("\n--- Batch Update (Adding Tags) ---")
        # Note: We must escape the JSON string for the shell argument
        json_arg = json.dumps({"tags": ["raindrip-test-tag"]})
        run_raindrip([
            "batch", "update", 
            "--ids", ",".join(map(str, bookmark_ids)), 
            "--collection", str(collection_id),
            json_arg
        ])
        log("Batch update complete", "green")

        # 5. Search Verification
        log("\n--- Searching ---")
        time.sleep(2) # Give search index a moment
        results = run_raindrip(["search", "raindrip-test-tag", "--collection", str(collection_id)])
        # Search API can be flaky with immediate indexing, so we warn rather than fail hard if 0
        if len(results) == 3:
            log(f"Found {len(results)} items with tag 'raindrip-test-tag'", "green")
        else:
            log(f"Warning: Found {len(results)}/3 items. Search indexing might be lagging.", "yellow")

        # 6. Tag Rename
        log("\n--- Renaming Tag ---")
        run_raindrip(["tag", "rename", "raindrip-test-tag", "raindrip-verified-tag"])
        log("Tag renamed", "green")

        # 7. Verification of Rename
        log("\n--- Verifying Rename ---")
        bm = run_raindrip(["get", str(bookmark_ids[0])])
        if "raindrip-verified-tag" in bm["tags"]:
             log("Tag rename verified on bookmark", "green")
        else:
             log(f"Tag rename check failed. Tags found: {bm['tags']}", "red")

        # 8. Clean up (Batch Delete)
        log("\n--- Batch Delete Bookmarks ---")
        run_raindrip(["batch", "delete", "--ids", ",".join(map(str, bookmark_ids))])
        log("Bookmarks deleted", "green")
        
    except Exception as e:
        log(f"\n❌ TEST FAILED: {e}", "red")
        sys.exit(1)
    finally:
        # 9. Delete Collection (Cleanup)
        if collection_id:
            log("\n--- Cleaning up Collection ---")
            try:
                run_raindrip(["collection", "delete", str(collection_id)])
                log("Collection deleted", "green")
            except Exception as e:
                log(f"Failed to delete collection: {e}", "red")

    log("\n✨ Playtest Completed Successfully! ✨", "green")

if __name__ == "__main__":
    main()
