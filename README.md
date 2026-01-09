# raindrip 💧

[![CI](https://github.com/rinvii/raindrip/actions/workflows/test.yml/badge.svg)](https://github.com/rinvii/raindrip/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AI-native CLI for Raindrop.io.

Designed for AI agents and automation scripts. Strict JSON output, robust error handling, and context-optimized commands.

## Key Features

- **🤖 AI-Native:** Default JSON output and high-level `context` commands.
- **📂 Hierarchy Support:** Create, move, and manage nested collections.
- **🖼️ Rich Metadata:** Access domain info, cover images, and media attachments.
- **📦 Batch Operations:** Bulk update or delete bookmarks efficiently.
- **🔍 Smart Search:** Beautiful tables for humans, compact JSON for agents.
- **✨ Icon Library:** Search and set collection icons from Raindrop's 10k+ library.

## Why raindrip? (AI-Native)

Traditional CLIs are built for humans to read. **raindrip** is built for **agents and automation scripts** to consume.

1.  **TOON-by-default:** Every command outputs strict, ultra-compact [TOON format](https://github.com/toon-format/toon) by default.
2.  **Token Efficiency:** TOON's tabular structure saves up to 60% on tokens compared to JSON, and 80%+ compared to raw API responses.
3.  **Smart Hints:** Error messages include `"hint"` fields that tell agents exactly how to fix the issue.
4.  **Dry Run:** Safe account management with a global `--dry-run` flag.

---

## Installation

```bash
uv tool install .
```

## Quick Start

1.  **Login** (Verifies token before saving)
    ```bash
    raindrip login
    ```

2.  **Account Overview** (The agent "situation report")
    ```bash
    raindrip context
    ```

## AI & Automation Usage

- **List Collections & Tags**
  ```bash
  raindrip structure
  ```

- **Collection Management**
  ```bash
  raindrip collection create "Work"
  # Search and set icons from Raindrop's 10k+ library
  raindrip collection set-icon <id> "robot"
  # Clean up empty collections
  raindrip collection clean
  ```

- **Tag Management**
  ```bash
  raindrip tag rename "old-tag" "new-tag"
  ```

- **Batch Operations**
  ```bash
  # Move bookmarks in bulk
  raindrip batch update --ids 1,2,3 '{"collection": {"$id": <target_id>}}'
  ```

*   **Search Bookmarks**
    ```bash
    # Ultra-compact TOON (Default)
    raindrip search "python"
    # Beautiful table for humans
    raindrip search "python" --pretty
    # Standard JSON
    raindrip search "python" --format json
    ```

- **Smart Sorting**
  ```bash
  # Suggest the best folder for a bookmark
  raindrip sort <id>
  ```

- **Get Schema** (For AI system prompts)
  ```bash
  raindrip schema
  ```

## Development

```bash
# Run tests
uv run pytest tests/
```
