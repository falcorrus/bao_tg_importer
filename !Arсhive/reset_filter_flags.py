#!/usr/bin/env python3
"""
Resets the is_event_filtered flag for all posts in Supabase.
"""

import asyncio
import os
import httpx
import sys

def print_header():
    print("="*60)
    print("SUPABASE POST FILTER RESET")
    print("Sets is_event_filtered to false for all posts.")
    print("="*60)

def print_success(message):
    print(f"✅ {message}")

def print_error(message):
    print(f"❌ {message}")

def print_info(message):
    print(f"ℹ️  {message}")

def load_config():
    """Загружает конфигурацию из .env или переменных окружения"""
    env_paths = ['.env', '../.env']
    
    for env_path in env_paths:
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value.replace('"', '').replace("'", "")
            break
        except FileNotFoundError:
            continue

    config = {
        'supabase_url': os.getenv('MY_SUPABASE_URL', '').strip(),
        'supabase_key': os.getenv('MY_SUPABASE_SERVICE_ROLE_KEY', '').strip()
    }

    missing = [key for key, value in config.items() if not value]
    if missing:
        print_error(f"Отсутствуют следующие переменные: {', '.join(missing)}")
        print("Пожалуйста, установите переменные окружения:")
        print("  MY_SUPABASE_URL, MY_SUPABASE_SERVICE_ROLE_KEY")
        return None
    
    return config

async def reset_flags():
    config = load_config()
    if not config:
        return

    print_info("Connecting to Supabase...")
    
    async with httpx.AsyncClient() as http_client:
        headers = {
            'apikey': config['supabase_key'],
            'Authorization': f"Bearer {config['supabase_key']}",
            'Content-Type': 'application/json',
            'Prefer': 'return=representation' # To get the count of updated rows
        }

        update_data = {
            'is_event_filtered': False
        }

        print_info("Resetting is_event_filtered flag for all posts...")
        
        try:
            # We target all rows by using a filter that will always be true,
            # like id not being null. Supabase requires a filter for updates.
            response = await http_client.patch(
                f"{config['supabase_url']}/rest/v1/posts?id=not.is.null",
                headers=headers,
                json=update_data,
                timeout=30.0
            )
            
            response.raise_for_status() # Raise an exception for bad status codes
            
            updated_posts = response.json()
            count = len(updated_posts)

            print_success(f"Successfully reset the flag for {count} posts.")

        except httpx.HTTPStatusError as e:
            print_error(f"HTTP Error occurred: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print_error(f"An error occurred: {e}")

def main():
    print_header()
    
    try:
        import httpx
    except ImportError as e:
        print_error(f"Missing required library: {e.name}")
        print("Please install dependencies with:")
        print("  pip install httpx")
        return

    asyncio.run(reset_flags())

if __name__ == '__main__':
    main()
