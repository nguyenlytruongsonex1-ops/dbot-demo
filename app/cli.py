import argparse
import json
from app.diagnosis.orchestrator import diagnose
from app.tools.registry import tool_metadata
from scenarios.run import SCENARIOS

def main() -> None:
    parser = argparse.ArgumentParser(description="CrewAI D-Bot demo")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("diagnose")
    d.add_argument("--scenario", choices=SCENARIOS, default="slow_query")
    d.add_argument("--context", default="")
    sub.add_parser("tools")
    sub.add_parser("scenarios")
    args = parser.parse_args()
    if args.command == "diagnose": print(diagnose(args.scenario, args.context).model_dump_json(indent=2))
    elif args.command == "tools": print(json.dumps(tool_metadata(), indent=2))
    else: print("\n".join(SCENARIOS))

if __name__ == "__main__": main()
