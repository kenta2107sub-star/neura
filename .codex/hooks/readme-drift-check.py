#!/usr/bin/env python3
"""progress.md と README の更新漏れがある commit を止める Codex hook。"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


TRIGGER = re.compile(
    r"^(design/.*\.md|package\.json|package-lock\.json|pnpm-lock\.yaml|"
    r"yarn\.lock|bun\.lockb?|requirements(?:-[^/]+)?\.txt|pyproject\.toml|"
    r"poetry\.lock|uv\.lock|Pipfile(?:\.lock)?|setup\.py|setup\.cfg|"
    r"\.env\.example|Gemfile(?:\.lock)?|go\.(?:mod|sum)|Cargo\.(?:toml|lock)|"
    r"manifest\.json|Dockerfile(?:\..*)?|(?:docker-)?compose[^/]*\.ya?ml|"
    r"\.devcontainer/.*|scripts/(?:setup|bootstrap)[^/]*|Makefile)$"
)
DRIFT_ENABLED = re.compile(r"^READMEドリフト検出：`有効`\s*$", re.MULTILINE)
UNSAFE_COMMIT_FLAGS = {"-a", "--all", "-o", "--only", "-i", "--include"}
COMMIT_OPTIONS_WITH_VALUE = {
    "-m",
    "--message",
    "-F",
    "--file",
    "--author",
    "--date",
    "--cleanup",
    "--trailer",
    "-c",
    "-C",
    "--fixup",
    "--squash",
    "-S",
    "--gpg-sign",
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def git_paths(cwd: Path, *args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args, "-z"],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {path for path in result.stdout.split("\0") if path}


def git_text(cwd: Path, object_name: str) -> str | None:
    result = subprocess.run(
        ["git", "show", object_name],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            ensure_ascii=False,
        )
    )


def find_git_commit(command: str, cwd: Path) -> tuple[Path, list[str]] | None:
    """Return the git working directory and commit arguments when detectable."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None

    for index, token in enumerate(tokens):
        if Path(token).name != "git":
            continue

        git_cwd = cwd
        cursor = index + 1
        while cursor < len(tokens):
            current = tokens[cursor]
            if current == "-C" and cursor + 1 < len(tokens):
                target = Path(tokens[cursor + 1])
                git_cwd = (target if target.is_absolute() else git_cwd / target).resolve()
                cursor += 2
                continue
            if current in {"-c", "--git-dir", "--work-tree", "--namespace"}:
                cursor += 2
                continue
            if current == "commit":
                return git_cwd, tokens[cursor + 1 :]
            if current.startswith("-"):
                cursor += 1
                continue
            break
    return None


def has_shell_chain(command: str) -> bool:
    # 改行で `git add` と `git commit` をまとめると、PreToolUse時点の
    # indexと実際のcommit対象がずれるため、引用符内も含めて禁止する。
    if "\n" in command or "\r" in command:
        return True
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        return any(token in {";", "&&", "||", "|", "&"} for token in lexer)
    except ValueError:
        return True


def has_nested_git_commit(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return True
    for index, token in enumerate(tokens[:-2]):
        if Path(token).name in {"bash", "sh", "zsh"} and tokens[index + 1] == "-c":
            return bool(re.search(r"(?:^|\s)(?:\S*/)?git\s+commit\b", tokens[index + 2]))
    return False


def unsafe_commit_mode(args: list[str]) -> str | None:
    """Require explicit staging so the hook can inspect the exact commit set."""
    cursor = 0
    while cursor < len(args):
        current = args[cursor]
        if current in UNSAFE_COMMIT_FLAGS or any(
            current.startswith(f"{flag}=") for flag in {"--only", "--include"}
        ):
            return current
        if current == "--":
            return "pathspec"
        if current in COMMIT_OPTIONS_WITH_VALUE:
            cursor += 2
            continue
        if current.startswith(("-m", "-F", "-S")) and len(current) > 2:
            cursor += 1
            continue
        if current.startswith("-"):
            cursor += 1
            continue
        return "pathspec"
    return None


def readme_drift_state(root: Path) -> tuple[bool, bool] | None:
    """Return (HEAD state, staged state), or None if staged progress is missing."""
    staged = git_text(root, ":progress.md")
    if staged is None:
        return None
    previous = git_text(root, "HEAD:progress.md") or ""
    return bool(DRIFT_ENABLED.search(previous)), bool(DRIFT_ENABLED.search(staged))


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return

    command = payload.get("tool_input", {}).get("command", "")
    if not isinstance(command, str):
        return

    if has_shell_chain(command) and re.search(r"\bcommit\b", command):
        deny(
            "git commitは他のコマンドと連結せず、単独のBash操作として実行してください。"
        )
        return
    if has_nested_git_commit(command):
        deny("bash -c等に入れ子にしたgit commitは実行できません。")
        return
    if re.search(r"--(?:git-dir|work-tree)(?:=|\s)", command) and re.search(
        r"\bcommit\b", command
    ):
        deny("git commitで--git-dirまたは--work-treeは使用できません。")
        return

    cwd = Path(payload.get("cwd") or ".").resolve()
    parsed = find_git_commit(command, cwd)
    if parsed is None:
        return

    git_cwd, commit_args = parsed
    root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=git_cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if root_result.returncode != 0:
        return

    root = Path(root_result.stdout.strip())
    if root.resolve() != PROJECT_ROOT:
        deny(
            "プロジェクト外または親リポジトリへのcommitは実行できません。\n"
            "このプロジェクトでgit initを完了し、プロジェクトルートから実行してください。"
        )
        return

    unsafe_mode = unsafe_commit_mode(commit_args)
    if unsafe_mode:
        deny(
            "品質ゲート判定のため、コミット対象を明示的にステージしてください。\n\n"
            f"使用できない指定: {unsafe_mode}\n"
            "git add で対象をステージした後、pathspec・-a・--only・--includeを付けずに"
            "git commitを実行してください。"
        )
        return

    changed = git_paths(
        root, "diff", "--cached", "--name-only", "--diff-filter=ACMRD"
    )
    if changed and "progress.md" not in changed:
        deny(
            "progress.mdがコミット対象に含まれていません。\n\n"
            "現在のフェーズ、決定事項、次のアクションを更新し、"
            "作業結果と同じコミットへ含めてください。"
        )
        return

    drift_state = readme_drift_state(root)
    if changed and drift_state is None:
        deny(
            "ステージ済みのprogress.mdを読み取れません。削除せず、"
            "作業結果と同じコミットへ含めてください。"
        )
        return
    if drift_state is None:
        return

    previously_enabled, staged_enabled = drift_state
    if previously_enabled and not staged_enabled:
        deny("READMEドリフト検出を有効から無効へ戻すことはできません。")
        return
    if not staged_enabled:
        return

    if not (root / "README.md").is_file():
        deny(
            "READMEドリフト検出が有効ですが、README.mdが存在しません。\n"
            "progress.mdの状態とPhase 8のREADME作成手順を確認してください。"
        )
        return

    if "README.md" in changed:
        return

    triggers = sorted(path for path in changed if TRIGGER.match(path))
    if not triggers:
        return

    listed = "\n".join(f"  - {path}" for path in triggers)
    deny(
        "README.md が未更新のため git commit を停止しました。\n\n"
        f"更新トリガー対象:\n{listed}\n\n"
        ".codex/flow.md の README 更新トリガー表を確認し、"
        "必要なセクションを更新してから再度コミットしてください。"
    )


if __name__ == "__main__":
    main()
