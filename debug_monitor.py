import aiohttp
import asyncio
import sys
import traceback

async def check_site():
    url = "https://lead.arztools.tech/checklead.php?id=4606"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    print(f"Checking {url}...", file=sys.stdout)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10, ssl=False) as resp:
                print(f"Status: {resp.status}", file=sys.stdout)
    except Exception as e:
        print(f"Error: {repr(e)}", file=sys.stdout)
        traceback.print_exc(file=sys.stdout)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_site())
