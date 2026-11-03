# agent-skills

自建 Agent skill 集合，一个目录一个 skill。纯 markdown 加 Python 标准库，拷进 skills 目录即可用。

## 通用

| skill | 用途 |
|---|---|
| [disk-cleanup](disk-cleanup/) | 磁盘满了：问清哪块盘 → 只读扫描出账 → 分档方案 → 点名后按清单清理 |
| [github-publish](github-publish/) | 项目发布：隐私闸门 → README 去 AI 味 → 版本号 → 推送与远端核验 |
| [dsh-wechat-bridge](dsh-wechat-bridge/) | 把 DSH 接到微信：扫码绑定 → headless 调用 → 崩溃守护、权限要人批的时机 |

## 论文：已拆为独立仓库

38 个论文 skill 移到了 [Northseacaviar/paper-workflow](https://github.com/Northseacaviar/paper-workflow)——流程骨架 6、写作与语言 9、审查与核验 13、图表与交付 10，附 14 个外部 skill 库的地址与取舍判断。

拆开的理由：它是一套互相调用的流程（路由 → 写作 → 核验 → 出图 → 投稿体检），跟着别的通用 skill 挤在一个仓库里，装的时候得自己挑目录。

## 安装

把 skill 目录整个拷进 agent 的 skills 目录，保持 `SKILL.md` + `scripts/` + `references/` 的结构：

- Hermes：`~/.hermes/skills/<skill>/`（或你配置的 skills 目录）
- Claude Code：`<project>/.claude/skills/<skill>/`

脚本只依赖 Python 3 标准库，无第三方包。

## 许可

MIT © @Northseacaviar。转载自第三方的 skill 见 [paper-workflow 的 ATTRIBUTIONS](https://github.com/Northseacaviar/paper-workflow/blob/main/ATTRIBUTIONS.md)。
