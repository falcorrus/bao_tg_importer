# LLM Task: Filter Telegram Posts with Ollama

## Problem Statement:
The goal is to filter "useful" event posts from Telegram messages imported into Supabase. Currently, the `bao_tg_importer.py` script imports all messages, but many are "junk" and not relevant events. An LLM (Ollama `gemma3:latest`) needs to be integrated into the workflow to classify messages as events or non-events.

## Current Status:
1.  **Telegram Import:** The `bao_tg_importer.py` Python script successfully fetches messages from Telegram and attempts to insert them into the `public.posts` table in Supabase.
2.  **LLM Setup:** A local Ollama instance is running, and the `gemma3:latest` model is installed and available.
3.  **Supabase Connection Issue:** The primary blocker is that the agent (me) is currently unable to connect to the Supabase database using the `execute_sql` tool, returning "Not connected" errors. This prevents:
    *   Verifying the current schema of the `public.posts` table.
    *   Adding new columns (`is_event_filtered`, `is_event`) to the `public.posts` table, which are necessary for storing LLM classification results.

## Proposed Integration Point:
Integrate the LLM filtering *within* the `bao_tg_importer.py` script, after fetching messages from Telegram but *before* inserting them into the `public.posts` table in Supabase.

## Next Steps (Blocked by Supabase Connection):
1.  **Resolve Supabase Connection:** The "Not connected" error for `execute_sql` must be resolved externally.
2.  **Verify `public.posts` Table Schema:** Once connected, confirm the exact schema of the `public.posts` table, especially the `channel_id` column type.
3.  **Add New Columns to `public.posts`:** Add `is_event_filtered` (BOOLEAN, DEFAULT FALSE) and `is_event` (BOOLEAN, DEFAULT FALSE) columns to the `public.posts` table.
4.  **Modify `bao_tg_importer.py`:**
    *   Add a function to call the local Ollama API (`http://127.0.0.1:11434/api/generate`) with `gemma3:latest`.
    *   For each fetched Telegram message, construct a prompt for the LLM to classify if it's an event.
    *   Based on the LLM's response, set the `is_event` flag for the post.
    *   Update the `posts_to_insert` logic to include the `is_event_filtered` and `is_event` values.
    *   Only insert messages that are classified as events (or all messages with the classification).
5.  **Schedule the script:** The script should be run periodically (e.g., via cron job) to continuously filter new Telegram messages.
