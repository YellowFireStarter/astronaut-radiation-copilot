"""End-to-end MCP test: spawns mcp_server.py over stdio and exercises the tools."""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def _project_from_env_file():
    """Read PROJECT from the mcp/.env file (no third-party deps)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    if key.strip() == "PROJECT":
                        return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


# PROJECT comes from the environment variable, or from mcp/.env (see .env.example).
PROJECT = os.getenv("PROJECT") or _project_from_env_file()
if not PROJECT:
    sys.exit(
        "PROJECT is not set. Create mcp/.env (see mcp/.env.example) with "
        "PROJECT=<absolute path to your project checkout>, or set the PROJECT "
        "environment variable."
    )
PYTHON = os.path.join(PROJECT, "backend", ".venv", "Scripts", "python.exe")


async def main():
    params = StdioServerParameters(command=PYTHON, args=["mcp/mcp_server.py"], cwd=PROJECT)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("REGISTERED TOOLS:", [t.name for t in tools.tools])
            print("=" * 60)

            calls = [
                ("get_spe_alert", {}),
                ("get_live_telemetry", {}),
                ("get_proton_flux", {"hours": 6}),
                ("get_kp_history", {"points": 144}),
                ("forecast_dose", {"orbit_type": "lunar_transit", "duration_days": 30}),
                ("assess_risk", {"orbit_type": "lunar_transit", "duration_days": 30,
                                 "crew_json": '[{"name":"CDR","age":40,"sex":"male"},{"name":"PLT","age":38,"sex":"female"}]'}),
                ("plan_mission", {"orbit_type": "lunar_transit", "duration_days": 30,
                                  "crew_json": '[{"name":"CDR","age":40,"sex":"male"}]'}),
                ("generate_brief", {"kind": "daily", "orbit_type": "leo_iss", "duration_days": 14,
                                    "crew_json": '[{"name":"CDR","age":40,"sex":"male"}]'}),
            ]
            for name, args in calls:
                try:
                    res = await session.call_tool(name, args)
                    text = res.content[0].text if res.content else "(no content)"
                    print(f"--- {name} ---")
                    print(text[:420])
                    print()
                except Exception as e:
                    print(f"--- {name} --- FAILED: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
