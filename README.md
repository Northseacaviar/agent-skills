# agent-skills

Agent 可用的 skill 集合，一个目录一个 skill。

| skill | 用途 |
|---|---|
| [disk-cleanup](disk-cleanup/) | 磁盘满了：问清哪块盘 → 只读扫描出账 → 分档方案 → 点名后按清单清理 |
| [github-publish](github-publish/) | 项目发布：隐私闸门 → README 去 AI 味 → 版本号 → 推送与远端核验 |

## 安装

把 skill 目录整个拷进 agent 的 skills 目录，保持 `SKILL.md` + `scripts/` + `references/` 的结构：

- Hermes：`~/.hermes/skills/<skill>/`（或你配置的 skills 目录）
- Claude Code：`<project>/.claude/skills/<skill>/`

脚本只依赖 Python 3 标准库，无第三方包。

## 许可

MIT © @Northseacaviar
