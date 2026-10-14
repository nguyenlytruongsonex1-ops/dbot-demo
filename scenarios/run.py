import argparse
import json
from app.scenarios import SCENARIOS, clear, state, trigger

def main() -> None:
    parser = argparse.ArgumentParser(description="D-Bot Light demo workload trigger")
    parser.add_argument("action", choices=["trigger", "clear", "state"])
    parser.add_argument("scenario", nargs="?", choices=SCENARIOS)
    args = parser.parse_args()
    if args.action == "trigger":
        if not args.scenario: parser.error("trigger requires a scenario")
        result = trigger(args.scenario)
    elif args.action == "clear": result = clear(args.scenario)
    else: result = {"state": state()}
    print(json.dumps(result, default=str, indent=2))

if __name__ == "__main__": main()
