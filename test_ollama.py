import httpx
import asyncio
import json

async def test_ollama():
    url = "http://127.0.0.1:11434/api/generate"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json={
                    "model": "gemma3:latest",
                    "prompt": "Say hello",
                    "stream": False
                },
                timeout=10.0
            )
            print(response.json())
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama())
