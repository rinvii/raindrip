# raindrip 💧

[![CI](https://github.com/rinvii/raindrip/actions/workflows/test.yml/badge.svg)](https://github.com/rinvii/raindrip/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AI-native CLI for Raindrop.io.

Designed for AI agents and automation scripts. **TOON** for maximum token efficiency, with optional JSON output for standard integrations.

## Key Features

- **🤖 AI-Native:** Outputs [TOON format](https://github.com/toon-format/toon) by default to save on context tokens.
- **📊 Situation Reports:** High-level `context` command for a quick "state of the world" overview.
- **📂 Hierarchy Support:** Create, move, and manage nested collections.
- **📦 Batch Operations:** Bulk update or delete bookmarks efficiently.

## Why raindrip? (AI-Native)

Traditional CLIs are built for humans to read. **raindrip** is built for **agents and automation scripts** to consume.

1.  **Tabular Efficiency:** TOON's structure handles large bookmark lists without the repetitive key-value overhead of JSON.
2.  **Context-First:** Commands like `context` and `structure` are designed to give an LLM exactly what it needs to understand your library in one shot.
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

## Usage Examples

- **List Collections & Tags**

  ```bash
  raindrip structure
  ```

- **Search Bookmarks**

  ```bash
  # TOON (Default)
  raindrip search "python"
  # Beautiful table for humans
  raindrip search "python" --pretty
  # Standard JSON
  raindrip search "python" --format json
  ```

- **Collection Management**

  ```bash
  raindrip collection create "Research"
  # Set icon from Raindrop's library
  raindrip collection set-icon <id> "robot"
  ```

- **Batch Operations**

  ```bash
  # Move bookmarks in bulk
  raindrip batch update --ids 1,2,3 '{"collection": {"$id": <target_id>}}'
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
