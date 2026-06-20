# Claude Code Reviewer MCP

Legacy note: this document is kept for users who have Claude Code. The default
workflow for this repository is now Codex as worker and VS Code Copilot Opus as
read-only reviewer. See `docs/copilot_opus_reviewer_mcp.md`.

Legacy Claude 流程采用“Codex 执行，Claude Code 审核”的分工。参考
`Auto-claude-code-research-in-sleep` / AutoResearchClaw 的思路，执行 agent
负责改代码和跑验证，Claude Code 通过 MCP 作为只读 reviewer 检查 diff、测试缺口和研究流程风险。

## 本机接入状态

如果要启用这条 legacy 路径，需要具备以下入口：

- Claude Code CLI: `claude`
- Codex CLI: `codex`
- Codex MCP server: `claude-review`

Codex 的全局 MCP 配置应包含类似内容：

```toml
[mcp_servers.claude-review]
command = "python3"
args = ["/path/to/claude-review/server.py"]
```

不要把个人 `~/.codex/config.toml`、API key、cookie 或凭据复制进仓库。

## 健康检查

先确认 CLI 可用：

```bash
which claude
claude --version
```

再由 Codex 侧调用 `mcp__claude_review.review` 做一次最小检查。如果返回
`Not logged in · Please run /login`，说明 MCP server 已接通，但 Claude Code
账号没有登录。打开交互式 Claude Code 并执行 `/login`，登录后重新发起 review。

## 使用流程

生成 reviewer prompt：

```bash
python scripts/build_claude_review_prompt.py \
  --reviewer-name "Claude Code" \
  --output tmp/claude_review_prompt.md
```

只审查本次接入相关文件：

```bash
python scripts/build_claude_review_prompt.py \
  --reviewer-name "Claude Code" \
  --paths AGENTS.md docs/claude_reviewer_mcp.md scripts/build_claude_review_prompt.py \
  --output tmp/claude_review_prompt.md
```

然后由 Codex 调用 MCP 工具：

```text
mcp__claude_review.review(prompt=<tmp/claude_review_prompt.md contents>, tools="")
```

`tools=""` 表示 Claude 只基于 prompt 审查，不直接读写工作区。若需要 Claude
自行读取文件，可在 Codex 侧显式放开只读工具，但 reviewer 仍不得修改文件。

## 阻断标准

Claude review 中出现以下情况时，Codex 必须先修复再交付：

- P0/P1 缺陷或明确的行为回归。
- 数据泄漏、未来函数、样本边界错误、预测 horizon 错位。
- 会破坏可复现实验的路径、依赖、随机性或数据输入问题。
- 可能泄露凭据、提交大文件、误删数据或执行破坏性命令。
- 文档命令明显无法运行。

如果 Claude review 未能运行，最终回复需要说明原因，并列出已经完成的本地验证。
