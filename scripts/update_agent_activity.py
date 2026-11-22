"""Update the GitHub profile's Markdown table from a local Roundtable JSONL log."""

import argparse
import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory


AGENTS = {
    "claude": "Claude Code",
    "codex": "Codex",
    "antigravity": "Antigravity",
}
OUTCOMES = {"success", "failure", "interrupted"}
START = "<!-- AGENT-ACTIVITY:START -->"
END = "<!-- AGENT-ACTIVITY:END -->"


def activity_table(log):
    requests = Counter()
    successes = Counter()
    tokens = Counter()
    conversations = {agent: set() for agent in AGENTS}
    with log.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            agent = row.get("agent")
            status = row.get("status")
            if not isinstance(agent, str) or agent not in AGENTS:
                continue
            if not isinstance(status, str) or status not in OUTCOMES:
                continue
            requests[agent] += 1
            successes[agent] += status == "success"
            conversation = row.get("conversation")
            if isinstance(conversation, str) and conversation:
                conversations[agent].add(conversation)
            usage = row.get("tokens")
            if isinstance(usage, dict):
                counts = (usage.get("input"), usage.get("output"))
                if all(type(count) is int and count >= 0 for count in counts):
                    tokens[agent] += sum(counts)

    if not requests:
        return None

    rows = [
        "| エージェント | トークン | 会話 | 依頼 | 正常終了 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for agent, name in AGENTS.items():
        total = f"{tokens[agent]:,}" if agent in tokens else "—"
        rows.append(
            f"| {name} | {total} | {len(conversations[agent]):,} | "
            f"{requests[agent]:,} | {successes[agent]:,} |"
        )
    return "\n".join(rows)


def update_readme(path, table):
    with path.open(encoding="utf-8", newline="") as source:
        original = source.read()
    before, start, remainder = original.partition(START)
    _, end, after = remainder.partition(END)
    if not start or not end or original.count(START) != 1 or original.count(END) != 1:
        raise ValueError(f"{path} に利用実績の開始・終了マーカーが1組必要です。")
    newline = "\r\n" if remainder.startswith("\r\n") else "\n"
    gap = newline * 2
    updated = before + START + gap + table.replace("\n", newline) + gap + END + after
    if updated == original:
        return False

    with TemporaryDirectory(dir=path.parent, prefix=".agent-activity-") as directory:
        staged = Path(directory) / path.name
        with staged.open("w", encoding="utf-8", newline="") as destination:
            destination.write(updated)
        staged.chmod(path.stat().st_mode & 0o777)
        staged.replace(path)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Roundtable runs.jsonl")
    parser.add_argument("--readme", type=Path, default=Path(__file__).resolve().parents[1] / "README.md")
    args = parser.parse_args()

    try:
        try:
            table = activity_table(args.log)
        except FileNotFoundError:
            table = None
        if table is None:
            print("集計できる利用記録がありません。")
        elif update_readme(args.readme, table):
            print("READMEの利用実績を更新しました。")
        else:
            print("利用実績に変更はありません。")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
