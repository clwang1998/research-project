# Copilot Opus Reviewer MCP

本项目采用“Codex 执行，GitHub Copilot Opus 审核”的分工。Codex 负责改代码、
跑验证、整理修改范围；Copilot Opus 只作为只读 reviewer 检查 diff、测试缺口
和研究流程风险。

默认不要让 Copilot CLI 同时当执行者改文件。当前设计是单 worker、多轮 reviewer：
Codex 持有工作区修改权，Copilot Opus 只给审查意见。

## 接入方式

GitHub Copilot Pro+/VS Code 里的 Opus 通常是 Copilot 会话中的可选模型，而不是
一个稳定的本地非交互 reviewer API。并且 Copilot CLI 可能只开放 GPT 模型，
即使 VS Code Copilot Chat 可以选择 Opus。因此本项目使用 ARIS 自带的
`manual-review` MCP 或等价的手动 prompt 交接：

1. Codex 生成 reviewer prompt。
2. 脚本把 prompt 复制到剪贴板，并在 `review-stage/` 创建评审结果和修改范围
   占位文件。
3. 将剪贴板内容粘贴到 VS Code Copilot Chat，并在 Copilot 中选择 Opus。
4. 将 Opus 的完整评审结果粘回占位文件。
5. 主流程继续修复、验证、复审，并保存每轮记录。

这种方式保留了 ARIS 的 review loop 和审计记录，同时不需要 Claude Code 账号。

## MCP 配置

项目级 `.mcp.json` 可以注册本地 `manual-review` MCP，供支持项目 MCP 的宿主
使用。`.mcp.json` 是本机配置并被 git 忽略；可提交模板见
`.mcp.json.example`。复制模板后，把路径改成本机 ARIS 副本：

```json
{
  "mcpServers": {
    "manual_review": {
      "command": "python3",
      "args": [
        "/Users/jackiewang/Documents/research project/external/Auto-claude-code-research-in-sleep/mcp-servers/manual-review/server.py"
      ],
      "env": {
        "MANUAL_REVIEW_SERVER_NAME": "manual_review",
        "MANUAL_REVIEW_MODE": "browser",
        "MANUAL_REVIEW_TIMEOUT_SEC": "86400"
      }
    }
  }
}
```

本机配置完成后可验证 JSON：

```bash
python -m json.tool .mcp.json
```

在支持 MCP 的宿主中确认存在 `manual_review`，并确认可用工具包含
`mcp__manual_review__review`。如果当前 Codex 运行环境没有暴露这个 MCP 工具，
直接使用下面的 prompt 文件手动交接。

## 使用流程

生成 reviewer prompt：

```bash
python scripts/prepare_copilot_opus_review.py
```

只审查少量文件：

```bash
python scripts/prepare_copilot_opus_review.py \
  --paths AGENTS.md docs/copilot_opus_reviewer_mcp.md docs/ten_page_technical_report_workflow.md scripts/build_claude_review_prompt.py scripts/build_reviewer_prompt.py scripts/prepare_copilot_opus_review.py
```

脚本会输出三个路径：

- `Prompt`：生成的 reviewer prompt。
- `Review response file`：把 Copilot Opus 完整回复粘贴到这里。
- `Scope file`：Codex 后续记录修复范围、验证和剩余风险。

如果 macOS `pbcopy` 可用，脚本会自动把 prompt 放进剪贴板。

然后调用 MCP：

```text
mcp__manual_review__review(
  prompt=<tmp/copilot_opus_review_prompt.md contents>,
  config={"model_reasoning_effort": "xhigh", "preferred_model": "copilot-opus"}
)
```

浏览器页面出现后，把 prompt 复制到 Copilot Opus 的新会话，要求它只读审查；
不要让 reviewer 修改文件。将完整评审粘回页面，等待 MCP 返回结果。

如果 MCP 工具不可用，直接打开 `tmp/copilot_opus_review_prompt.md`，复制全文到
VS Code Copilot Chat，模型选择 Opus。收到评审后，把完整回复保存为：

```text
review-stage/YYYYMMDD-HHMM-roundNN-copilot-opus.md
```

同一轮修复完成后，在同目录新增一个范围记录：

```text
review-stage/YYYYMMDD-HHMM-roundNN-scope.md
```

## ARIS 工作流

安装 ARIS Copilot skills 后，review 型工作流可以直接使用 manual reviewer：

```text
/research-review "paper/ or changed files" — reviewer: manual
/auto-review-loop "scope" — reviewer: manual, difficulty: hard
```

`difficulty: nightmare` 依赖 Codex exec 直接读仓库，不适合 manual backend。使用
Copilot Opus reviewer 时选择 `medium` 或 `hard`。

## 阻断标准

Copilot Opus review 中出现以下情况时，Codex 必须先修复再交付：

- P0/P1 缺陷或明确的行为回归。
- 数据泄漏、未来函数、样本边界错误、预测 horizon 错位。
- 会破坏可复现实验的路径、依赖、随机性或数据输入问题。
- 可能泄露凭据、提交大文件、误删数据或执行破坏性命令。
- 文档命令明显无法运行。

如果 MCP 未能运行，但 Copilot 可用，手动把 prompt 发给 Copilot Opus，并把回复
保存到 `review-stage/`。如果 Copilot Opus 也不可用，最终回复需要说明原因，并
列出已经完成的本地验证。
