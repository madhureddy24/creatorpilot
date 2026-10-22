"""CreatorPilot: a stateful MCP server (Streamable HTTP) for planning short-form content."""
import json, os, sqlite3, datetime
from mcp.server.fastmcp import FastMCP

DB = os.environ.get("CREATORPILOT_DB", "creatorpilot.db")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")  # set to a Bedrock model you have access to
REGION = os.environ.get("AWS_REGION", "us-east-1")

mcp = FastMCP("CreatorPilot", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))


def db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS ideas(id INTEGER PRIMARY KEY, text TEXT, created TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY, plan TEXT, created TEXT)")
    return con


def llm(prompt: str):
    """Call Amazon Bedrock (Converse API). Returns None if not configured so the demo never breaks."""
    if not MODEL_ID:
        return None
    try:
        import boto3
        client = boto3.client("bedrock-runtime", region_name=REGION)
        r = client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 1200, "temperature": 0.7},
        )
        return r["output"]["message"]["content"][0]["text"]
    except Exception as e:  # log this in FRICTION_LOG.md
        print("Bedrock error:", e)
        return None


@mcp.tool()
def save_idea(text: str) -> str:
    """Save a content idea so the creator never loses it."""
    con = db()
    con.execute("INSERT INTO ideas(text, created) VALUES (?, ?)", (text, datetime.datetime.now().isoformat()))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
    return f"Saved. You now have {n} ideas."


@mcp.tool()
def get_history() -> dict:
    """Return all saved ideas and the most recent weekly plan."""
    con = db()
    ideas = [r[0] for r in con.execute("SELECT text FROM ideas ORDER BY id")]
    row = con.execute("SELECT plan FROM plans ORDER BY id DESC LIMIT 1").fetchone()
    return {"ideas": ideas, "last_plan": json.loads(row[0]) if row else None}


@mcp.tool()
def plan_week(posts_per_week: int = 5) -> dict:
    """Plan a week of short-form posts using saved ideas and the previous plan. Returns a calendar card."""
    hist = get_history()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][: max(1, min(posts_per_week, 7))]
    prompt = (
        "You are a short-form video content planner. Using these saved ideas, plan one post per day "
        f"for {days}. Avoid repeating the last plan. Return ONLY JSON: "
        '[{"day":"Mon","title":"...","hook":"..."}]\n'
        f"Ideas: {hist['ideas']}\nLast plan: {hist['last_plan']}"
    )
    out = llm(prompt)
    try:
        plan = json.loads(out.strip().strip("`").removeprefix("json").strip()) if out else None
    except Exception:
        plan = None
    if not plan:  # fallback so the demo always works
        ideas = hist["ideas"] or ["Share a quick tip from your week"]
        plan = [{"day": d, "title": ideas[i % len(ideas)], "hook": f"Nobody tells you this about: {ideas[i % len(ideas)]}"}
                for i, d in enumerate(days)]
    con = db()
    con.execute("INSERT INTO plans(plan, created) VALUES (?, ?)", (json.dumps(plan), datetime.datetime.now().isoformat()))
    con.commit()
    return {"type": "calendar_card", "plan": plan}


@mcp.tool()
def draft_script(title: str, seconds: int = 30) -> str:
    """Draft a hook + beats + call-to-action script for one post."""
    out = llm(f"Write a {seconds}-second short-form video script for '{title}'. Give: hook, 3 beats, call to action. Be concise.")
    return out or f"HOOK: Stop scrolling, this is about {title}.\nBEAT 1: The problem.\nBEAT 2: The fix.\nBEAT 3: Proof.\nCTA: Follow for the next one."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")  # serves at http://localhost:8000/mcp
