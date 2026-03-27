#!/usr/bin/env python3
import asyncio
import sys


async def test_llm():
    print("Testing LLM server connection...")
    print("=" * 50)

    try:
        from agents.llm_client import OpenCodeLLMClient

        client = OpenCodeLLMClient(
            system_prompt="You are a helpful assistant. Be concise.",
        )

        print("1. Initializing client... OK")

        print("\n2. Testing text completion...")
        response = await client.complete(
            "What is 2+2? Answer with just the number.",
            max_retries=0,
        )
        print(f"   Response: '{response}'")

        if "4" in response:
            print("   OK Text completion working")
        else:
            print("   FAIL Unexpected response (expected '4')")
            return False

        await client.disconnect()
        print("\n3. Disconnecting... OK")

        print("\n" + "=" * 50)
        print("All tests passed! LLM server is working correctly.")
        return True

    except Exception as e:
        print(f"\nError: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_llm())
    sys.exit(0 if success else 1)
