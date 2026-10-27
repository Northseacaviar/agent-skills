---
name: github-publish
description: "Use when 要把项目推上 GitHub 或发新版本。先过隐私闸门，再润色说明、定版本号，最后用远端数据核验。"
version: 1.0.0
author: Corvin Hermes
license: MIT
metadata:
  hermes:
    tags: [github, release, privacy, semver, readme, gh-cli]
    related_skills: [vibecoding-workflow, repo-privacy-audit, github-personal-info-cleanup]
---

# GitHub 发布：项目交出去之前的八道工序

一条总原则：**仓库里的每个字都按「陌生人会看到」来审**。README、代码注释、commit
message、tag 说明、release notes、仓库 description、issue 模板，全是公开文字，写法一样。
`private` 只降低曝光，不改变「它会被别人读到」这件事。

八道工序按顺序走。前五道完成之前不要 push —— 推上去的凭据就算删掉也留在历史里。

## 何时用

- 新项目第一次上 GitHub；已有项目发新版本；私有仓库转公开。
- 「帮我传到 github」「发个版」「这个 README 太长/太 AI 了」。
- 不适用：只读审计别人的仓库（那是 `repo-privacy-audit`）；清理已泄露的历史凭据且要重写历史（先按本 skill 第 1 道工序出报告，再让用户拍板）。

## 工序 0：五分钟对齐

先问清三件事，缺一件就停：

1. **谁看这个仓库**：公开项目（陌生人 + 潜在使用者）/ 私有（自己或协作者）/ 私有但以后要公开。
2. **这次是首发还是发版**：首发要建骨架，发版只走版本号 + tag + release。
3. **交付物是什么**：源码？发布件？只要 README？

```bash
git log --oneline -5          # 有没有别人（另一个 AI/协作者）刚提交
git tag -l                    # 已有版本，避免撞号
git branch --show-current
gh api repos/<owner>/<repo> --jq .default_branch   # 分支名不一致会误推新分支
git config user.name && git config user.email      # 身份必须是公开账号
```

身份统一成 GitHub 账号名 + noreply 邮箱：

```bash
git config user.name  "Northseacaviar"
git config user.email "<id>+<login>@users.noreply.github.com"
```

## 工序 1：隐私闸门（最重要的一道）

四层都要过，只看工作区等于没查。

```bash
python scripts/privacy_scan.py .                 # 已跟踪文件
python scripts/privacy_scan.py . --all-files     # 连未跟踪的一起，防止下次 git add -A 带上去
python scripts/privacy_scan.py . --history --json scan.json   # 全历史 blob（删掉的文件仍在这里）
python scripts/doc_lint.py README.md --strict    # 顺带查机器路径与本地 docs 链接
```

默认只报 medium 及以上；`--min-severity low` 连「盘符绝对路径」这类示例一起报。仓库自己的
文档在讲解这些模式时会命中自己，用根目录的 `.privacyignore` 按路径放行（只放行讲解用的 md
与规则脚本，功能代码与夹具照扫）。

扫描器认这些：Windows/Unix 用户目录、`file:///`、盘符绝对路径、邮箱、GitHub/OpenAI/AWS/
Google/Slack/GitLab 凭据、私钥块、`password=…` 之类硬编码、手机号与身份证号、内网 IP、
本机代理端口、`DESKTOP-XXXX` 主机名、`.hermes`/`state.db`/`ai-bridge` 这类工具链路径、
以及「拍板 / 复盘 / 审查报告 / 成本账 / 子 agent / 按用户要求」这类内部叙述。

### 三分类判定，不是命中就删

| 类别 | 处理 |
|---|---|
| **技术必需** | 留：产品自身的 `127.0.0.1:8080`、包名、CDN/仓库地址、公开文档链接、License、`@账号名` 署名 |
| **私人信息** | 改：真名/昵称、本机路径与用户名、主机名、内网 IP、代理端口、邮箱、凭据、真机抓包样本 |
| **内部叙述** | 删：谁在哪天拍板、审查编号、复盘/成本账/学习报告的存在、AI 工具分工 |

测试夹具里的真机数据要换成**同形态假值**（uid 位数、时间戳格式、颜色值都保持一致），
改完重跑测试证明形态没破——这是判断「脱敏有没有把功能改坏」的唯一证据。

### 凭据的特殊处理

- 一旦进过公开历史，**当作已泄露**：先去平台吊销/轮换，再谈清历史。清历史不等于没泄露过。
- 重写历史是用户的决定，不是你的：列三档（只堵未来 / 重写强推 / 删库重建）与代价，
  说明「强推后旧提交仍可按 SHA 取到」，等用户拍板。
- 未跟踪也要点名忽略：`.gitignore` 里写死探针、`docs/`、`.env`，然后 `git status --short` 复核。

### 元数据面

仓库 description、topics、website、About、profile bio、Gists、Releases、Pages、deploy keys
都要看一眼。仓库 description 里写「我的学习记录」这类句子，和 README 里写一样是公开信息。

## 工序 2：README 与说明文档（最少必要信息 + 去 AI 味）

**只回答四个问题**：这是什么 / 怎么装 / 怎么用 / 怎么测。其余默认删。

不写进 README 的：架构原理、为什么这样设计、踩过的坑、开发过程、成本、审查记录、
「本项目旨在」。这些属于代码注释与本机笔记。

结构模板见 `references/readme-template.md`（工具型 / 库型 / release notes 三种）。

### 去 AI 味清单（中文）

1. 删掉「旨在、致力于、赋能、助力、一站式、全方位、闭环、抓手、底层逻辑」。
2. 删掉「首先 / 其次 / 最后」「综上所述」「值得注意的是」这类连接骨架——直接说事。
3. 拆掉「不仅……而且」「不是……而是」：两句各说一件事。
4. 小标题后面不要先写一句总起句再说正事（那是凑字数）。
5. 不加 🌟🚀✅ 之类小标题表情；不用 `- **性能**：……` 的伪列表。
6. 不写意义与展望（「具有重要意义」「未来可期」）；不写「让我们一起」。
7. 数字给真值：写「首次启动约 1.2 s」，不写「性能显著提升」。
8. 通读一遍念出声：念着别扭的句子，删或改短。

英文那边同一套：`serves as` 改 `is`；`leverage` 改 `use`；`seamless/robust/pivotal/
comprehensive` 换成具体说法；少用 em dash；不加粗堆重点；标题不用 Title Case。

```bash
python scripts/doc_lint.py README.md --strict   # 命中短语、破折号密度、伪列表、无版本号
```

工具只报线索，最后判断靠读。改完用 `wc -c` 记下改前改后长度——「压缩到一半」这种要求要能自证。

### 署名

只写 `[@账号名](https://github.com/账号名)`。不写真名、昵称、AI 助手名、所用 agent、
「AI 结对开发」这类分工。代码文件头不写署名，只留一行版本事实（`/*! 工具名 v1.2.0 */`）。

## 工序 3：版本号

SemVer，三处一致、两处外部：

| 改哪一位 | 判据 | 例子 |
|---|---|---|
| MAJOR | 对外接口/配置/数据格式不兼容 | 1.4.2 → 2.0.0 |
| MINOR | 加功能，旧用法仍有效 | 1.4.2 → 1.5.0 |
| PATCH | 只修 bug、改文案、补文档 | 1.4.2 → 1.4.3 |
| 0.x | 还没稳定，接口随时改；0.x 阶段 MINOR 可以带破坏性改动 | 0.3.11 → 0.4.0 |

- 三处：代码里的版本常量、包元数据（`package.json` / `pyproject.toml` / `Cargo.toml` /
  插件头）、README 的版本表或首行。
- 两处外部：`git tag -a vX.Y.Z -m "vX.Y.Z"`、GitHub Release（正文从 CHANGELOG 摘）。
- 发版前 `git tag -l` 查号，撞号先协商；**已发布的 tag 不移动**——CDN 会缓存 `@tag`，
  移动 tag 等于制造版本横跳。
- 版本号要出现在用户看得见的地方（界面标题、`--version`、控制台一行）。用户报「还是老版本」
  时，第一句问的是「你界面上显示哪一版」，不是去翻代码。

## 工序 4：仓库骨架

```
README.md          必须
LICENSE            必须（MIT + 账号名，年份写当年）
.gitignore         必须：构建产物、依赖目录、.env、本机 docs/、探针与夹具
.gitattributes     建议：* text=auto；*.py / *.md 用 eol=lf，避免 Windows 提交把整文件改成 CRLF
CHANGELOG.md       可选，Keep a Changelog 格式，发版时加一节
.github/workflows/ 可选，跑测试
```

`git add -A` 之前先 `git status --short` 逐项看——探针、临时 JSON、成本账就是这么被带上去的。

## 工序 5：提交

**一条提交一个目的。** 修 bug 和改文案不要混在一起，否则回滚时只能整块回滚。

message 规范：

```
<type>(<scope>): <主题，祈使句，≤50 字>

为什么这么改（1–3 行）。不写"用户要求""按反馈调整"这类元叙述。
```

`type`：`feat` `fix` `docs` `chore` `refactor` `test` `perf` `build` `ci`。

提交前跑一次：`privacy_scan.py .` + 项目测试。失败就别提交，别用 `--no-verify` 绕——
纯文档改动要绕时，在 message 里注明「不含可执行代码」。

## 工序 6：推送与发布

```bash
gh repo create <name> --public --description "<一句话>" --source . --remote origin --push
# 已有仓库
git push origin main
```

发布：

```bash
gh release create v1.2.0 --title "v1.2.0" --notes-file notes.md
# 有产物时：gh release create v1.2.0 dist/app.zip --title ... --notes-file notes.md
```

- Release notes 写「这一版改了什么、怎么升级」，不写「本次迭代的思考过程」。
- 私有转公开：`gh repo edit --visibility public --accept-visibility-change-consequences`，
  前提是工序 1 的历史扫描已经过了。
- 走 CDN 的项目（jsdelivr 等）发版末步 purge，且文档里的地址钉 `@vX.Y.Z`，不要用分支引用。

## 工序 7：远端核验（读回才算完）

```bash
gh api repos/<owner>/<repo> --jq '{name,visibility,default_branch}'
gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1 -q '.tree[].path'   # 树里没有 docs/、.env
gh api repos/<owner>/<repo>/contents/README.md -q '.size'                  # 与本地 wc -c 对得上
gh release view v1.2.0 --json tagName,assets -q '.tagName'
gh api repos/<owner>/<repo>/commits/HEAD --jq '.sha'
```

`curl raw.githubusercontent.com` 报 `000` 或空body多半是本机 TLS/代理问题，不是文件缺失——
换 `gh api` 或浏览器复核，别据此改仓库。

核验项：远端树、README 渲染、链接 200、Release 与 tag 指向同一提交、Actions 绿、
包元数据版本号一致。

## 工序 8：交付报告

给用户三段，不超过一屏：

```
已发布：https://github.com/<owner>/<repo>（public，main，v1.2.0）
隐私：扫描 N 个文件 / M 个历史 blob，命中 K 处，已处理 K 处（列出规则名与文件）
版本：代码常量、package.json、README、tag、release 五处都是 1.2.0
未处理：历史里的 X（需要你拍板重写历史），旧 SHA 仍可取
```

## 四条硬红线

1. **凭据不进仓库，也不进对话**：发现泄露先去平台吊销，再谈清理；需要 token 时让用户自己完成。
2. **不替用户决定重写历史**：force push、filter-repo、删库都先说代价等用户点头。
3. **不把本机信息"抽象化"了事**：`C:\Users\<我>\…` 改成 `C:\Users\<name>\…` 仍要报给用户，
   由用户决定是保留示例还是删掉整段。
4. **不谎报核验**：没跑通的命令就说没跑通；远端读回失败时给失败证据，不给"应该已经好了"。

## 常见坑

- **半截克隆**：中断的 clone 会留下空 `.git`，`[ -d .git ]` 通过但命令全失败；用
  `git -C <dir> rev-list --count HEAD` 有输出才算可用。
- **MSYS 路径喂原生程序**：`git -C /d/foo` 报 `cannot change to`，要写 `D:/foo`。
- **schannel 握手失败**：`fatal: unable to access … schannel` 时用
  `git -c http.sslBackend=openssl push`（或全局设一次）。
- **CRLF 批量改写**：脱敏编辑时用 `newline=''` 读写保原行尾，否则一次提交全文件重写。
- **filter-repo 的 `--path 'docs/*'` 静默不生效**：用 `--path docs` 或 `--path-glob 'docs/*'`；
  它还会删掉 origin remote，重写后记得加回来。
- **jsdelivr 无 ref 地址解析的是最新 tag**，不是 main；发版后无 ref 仍是旧版是正常现象。
- **同一仓库两个 AI 并行改**：动手前 `git log -5`、打 tag 前 `git tag -l`。

## 提示词（可直接复制使用）

### P1 发布前隐私审查

> 你是发布前审查员，只读不动手。仓库在 `<路径>`，目标是 `<public/private>`。
> 1. 跑 `python scripts/privacy_scan.py . --all-files --history --json scan.json`；
> 2. 逐条读命中，按「技术必需 / 私人信息 / 内部叙述」三分类；技术必需要写出为什么必需
>    （产品自身端口、包名、公开 URL、署名）；
> 3. 对每条私人信息给出改法：替换成什么、影响哪些测试；
> 4. 单独列「仅存在于历史」的条目，注明文件与行，并说明要清需要重写历史；
> 5. 末尾输出：命中总数 / 需改 / 需删 / 可留 / 要用户拍板的条数。不要修改任何文件。

### P2 README 重写

> 读 `<README 路径>` 与项目入口代码，重写一份给陌生人看的 README。
> 只回答：这是什么（一句话 + 一段）、怎么装、怎么用（可复制命令）、怎么测、
> 版本与许可。删掉设计原理、背景、踩坑记录、成本与过程叙述。
> 语言要求：不用「旨在/赋能/助力/一站式/不仅…而且/首先其次最后/综上所述」；
> 不写意义与展望；不加表情符号与伪列表；数字给真值；句子长短交替，读出声不别扭。
> 保留：安装命令、真实 URL、版本号、`@账号名` 署名。
> 输出改后全文 + 一句话说明删了什么、为什么删；长度用 `wc -c` 对比改前。

### P3 提交信息

> 根据 `git diff --staged` 生成提交信息。格式 `<type>(<scope>): 主题`，
> 主题 ≤50 字、祈使句、说做了什么；正文 1–3 行说为什么。不要提用户、需求、
> 对话过程、AI 工具。若这次提交混了多个目的，先把它拆成几条提交建议。

### P4 发版核验

> 版本号 vX.Y.Z 已推。用 gh api 逐项核验并贴原始输出：远端树（确认没有本机文件）、
> README 大小与本地一致、tag 指向的 commit、release 是否存在及其 assets、
> 包元数据版本、Actions 最近一次运行的结论。
> 任一项失败就写「失败 + 证据 + 下一步」，不要用「应该没问题」收尾。

## 配套

- `scripts/privacy_scan.py` — 隐私与机器信息扫描（工作区 / 未跟踪 / 全历史），只读。
- `scripts/doc_lint.py` — README 的 AI 味与发行信息检查（版本号、安装/使用/许可、伪列表）。
- `tests/` — 两个脚本的自测，`python tests/test_privacy_scan.py` 可直接跑。
- `references/readme-template.md` — 工具型 / 库型 README 与 release notes 模板。
