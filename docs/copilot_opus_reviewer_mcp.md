# Copilot Opus Reviewer MCP

本项目采用“Codex 执行，GitHub Copilot Opus 审核”的分工。Codex 负责改代码、
跑验证、整理修改范围；Copilot Opus 只作为只读 reviewer。注意：这里的 Opus
review 不是普通代码审查。最终交付物是 paper/report，因此 Opus 应主要扮演
senior quant researcher / quant PM，评审论文方法、实验设计、结果解释、alpha
叙事和结论可信度；代码和脚本只作为支撑这些论文结论的复现证据来检查。

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

## 云端 ARIS 用法

如果本机 Codex runtime 没有暴露 `mcp__manual_review__review`，但云端 ARIS 环境
可以使用 manual-review MCP，就在云端 clone 或更新本仓库，并以同一分支作为
迭代源：

```bash
git clone https://github.com/clwang1998/research-project.git
cd research-project
git checkout codex/supervised-gat-ensemble-search
git pull --ff-only
```

云端 ARIS 只负责 review loop 和后续 paper/report 迭代，不要把 Copilot 当成第二个
写代码的 executor。每轮先同步分支，生成 review prompt，再由 Opus 只读评审；Codex
根据评审意见修改、验证、commit、push，云端再 `git pull --ff-only` 同步。

Opus 的默认身份必须是 paper-first reviewer：

- 从 quant PM / senior quant researcher 角度审 headline 是否可信。
- 检查 benchmark、walk-forward 选择、validation/test 分离、交易成本、换手率、
  capacity、regime、消融实验、negative controls 是否足够支撑结论。
- 判断统计提升是否可能只是搜索噪声、幸存者偏差或口径选择。
- 检查失败模型是否被诚实降级，图/Kronos/MLP 等复杂方法是否被过度包装。
- 最后再检查代码、命令、路径和复现风险。

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

给 Opus 的自然语言任务应明确写成 paper review，例如：

```text
You are reviewing the final quant research report as a senior quant PM, not as
a coding assistant. Judge whether the paper's methodology, experiments,
benchmarks, ablations, transaction-cost backtests, survivorship-bias treatment,
and conclusions are credible enough for submission. Return blocker findings
first, then concrete paper/report fixes. Treat code only as supporting evidence
for reproducibility.
```

## 阻断标准

Copilot Opus review 中出现以下情况时，Codex 必须先修复再交付：

- 论文 headline、主实验、benchmark 或结论与证据不匹配。
- 统计提升缺少稳定性、消融、negative control、成本/换手或 regime 支撑。
- P0/P1 缺陷或明确的行为回归。
- 数据泄漏、未来函数、样本边界错误、预测 horizon 错位。
- 会破坏可复现实验的路径、依赖、随机性或数据输入问题。
- 可能泄露凭据、提交大文件、误删数据或执行破坏性命令。
- 文档命令明显无法运行。

如果 MCP 未能运行，但 Copilot 可用，手动把 prompt 发给 Copilot Opus，并把回复
保存到 `review-stage/`。如果 Copilot Opus 也不可用，最终回复需要说明原因，并
列出已经完成的本地验证。
