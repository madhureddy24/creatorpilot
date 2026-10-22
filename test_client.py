import asyncio
try:
    from mcp.client.streamable_http import streamable_http_client as client_fn
except ImportError:
    from mcp.client.streamable_http import streamablehttp_client as client_fn
from mcp import ClientSession


async def main():
    async with client_fn("http://localhost:8000/mcp") as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

            async def call(name, args=None):
                r = await s.call_tool(name, args or {})
                print(f"\n--- {name} ---")
                print(r.content[0].text)

            await call("save_idea", {"text": "exam week study hacks"})
            await call("save_idea", {"text": "day in the life of a BTech student"})
            await call("get_history")
            await call("plan_week", {"posts_per_week": 5})
            await call("draft_script", {"title": "exam week study hacks"})


asyncio.run(main())
