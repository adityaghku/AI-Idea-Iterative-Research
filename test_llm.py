#!/usr/bin/env python3
import asyncio
import os
import sys
import httpx
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")


async def test_llm() -> bool:
    print("Testing OpenCode HTTP API (opencode-ai)...")
    print("=" * 50)

    try:
        print("1. Initializing client... OK")

        print("\n2. Testing text completion...")
        
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post("http://localhost:54321/session", json={})
            sid = resp.json()["id"]
            
            await client.post(f"http://localhost:54321/session/{sid}/message", json={
                "parts": [{"type": "text", "text": "What is 2+2? Answer with just the number."}],
                "model": {"providerID": "opencode", "modelID": "minimax-m2.5-free"}
            })
            
            for _ in range(30):
                await asyncio.sleep(2)
                resp = await client.get(f"http://localhost:54321/session/{sid}/message")
                msgs = resp.json()
                for m in msgs:
                    if m.get("info", {}).get("role") == "assistant":
                        for part in m.get("parts", []):
                            if part.get("type") == "text":
                                text = part.get("text", "")
                                print(f"   Response: {text!r}")
                                if "4" in text:
                                    print("   OK Text completion working")
                                    print("\n3. Closing... OK")
                                    print("\n" + "=" * 50)
                                    print("All tests passed! OpenCode HTTP client is working.")
                                    return True
                print(f"  Waiting... ({len(msgs)} messages)")
        
        print("   FAIL No assistant response")
        return False

    except Exception as e:
        print(f"\nError: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_llm())
    sys.exit(0 if success else 1)
