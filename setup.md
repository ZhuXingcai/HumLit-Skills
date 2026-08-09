# HumLit Skills — Auto Install

You are an AI agent. Follow these steps to install HumLit Skills.

## Steps

1. Detect the platform and set the target skill directory:

   | Platform | Target Path |
   |----------|-------------|
   | **Cursor** (Windows) | `$env:USERPROFILE\.cursor\skills\humlit-skills` |
   | **Cursor** (macOS/Linux) | `~/.cursor/skills/humlit-skills` |
   | **Codex** | `~/.codex/skills/humlit-skills` |
   | **Claude Code** | `~/.claude/skills/humlit-skills` |
   | **TRAE** | `~/.trae-cn/skills/humlit-skills` |
   | **Gemini CLI** | `~/.gemini/skills/humlit-skills` |
   | **Other** | Ask the user where to install |

2. Resolve a Python 3.9+ interpreter. Prefer `$PYTHON`, then `py -3` on
   Windows, then `python3`, then `python`. Reuse the resolved command as
   `<python>` for every following step.

3. If the target directory already exists:
   - Check if it's a git repo (`git -C <target_path> rev-parse --is-inside-work-tree`)
   - If yes and `git -C <target_path> status --porcelain` is empty: run
     `git -C <target_path> pull --ff-only`, skip the clone step, and continue
     with dependency installation and verification
   - If yes but it has local changes: do not overwrite or pull; report the
     changed files and ask the user how to proceed
   - If not a git repo: tell the user "HumLit Skills 已安装（非 git 安装，如需更新请重新下载）" and stop.

4. Clone the repository (Gemini CLI can also use `gemini skills install`):

   ```bash
   git clone https://github.com/ZhuXingcai/HumLit-Skills <target_path>
   ```

5. Install Python dependencies with the resolved interpreter:

   ```bash
   <python> -m pip install -r <target_path>/scripts/requirements.lock
   <python> -m pip install --no-deps <target_path>
   ```

6. Verify by running:

   ```bash
   humlit --version
   <python> <target_path>/scripts/literature.py check
   ```

7. When the user wants to share the same checkout with additional installed
   clients, register it without duplicating the repository:

   ```bash
   <python> <target_path>/scripts/register_skill.py \
     --source <target_path> --client codex --client claude --client trae
   ```

   Existing different targets are never overwritten.

8. Tell the user:
   "HumLit Skills 安装完成！开启新会话后，直接说'帮我搜论文'即可使用。"
