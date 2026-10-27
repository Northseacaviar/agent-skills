---
name: disk-cleanup
description: "Use when 磁盘不够用、要清 C/D 盘或某个目录。先问哪块盘，只读扫描出账，分档给方案，用户点名后才按清单删。"
version: 1.0.0
author: Corvin Hermes
license: MIT
metadata:
  hermes:
    tags: [disk, cleanup, windows, cache, powershell, safety]
    related_skills: [windows-system-diagnostics]
---

# 磁盘清理：问盘 → 量账 → 他选 → 按单删

清理是**不可逆**动作。整套流程的目的不是"帮你腾空间"，是让每一 GB 的去向都能被指认：
谁占的、删了会怎样、删的是哪一条路径。四步走完之前，一个文件都不动。

## 何时用

- 「C 盘满了」「磁盘不够了」「帮我清理一下」「哪个文件夹这么大」。
- 装软件/更新系统报空间不足，要先腾固定大小。
- 只想看账不想动手：只做第 1–2 步，第 2 步末尾明确说「我一项都没碰」。

不适用：机器变慢、风扇狂转这类性能问题（那是另一套取证）；磁盘报 SMART 错误/异响（硬件故障，先备份）。

## 四条铁律

1. **不猜是哪块盘。** 多盘机器上「C 盘满了」也可能该清的是 D 盘上的缓存。先列盘符表，让他点名。
2. **扫描阶段只读。** 第 2 步跑完之前，不删、不移、不清空回收站，连"顺手删个临时文件"都不做。
3. **逐项授权。** 他只对报过编号的那几项授权。名单外的一律不碰，也不"顺便优化一下"。
4. **数字要对得上。** 扫到的总量、系统报的已用、删前删后的可用，三个数都要报，差值单独解释，不用「其他」凑齐。

---

## 第 1 步 问清：哪块盘、腾多少、不能动什么、授权到哪一档

先量盘，后问话。盘符表要带容量和可用，他才能选：

```bash
df -h          # git-bash / Linux / macOS
```
```powershell
Get-PSDrive -PSProvider FileSystem | Select Name,@{n='UsedGB';e={[math]::Round($_.Used/1GB,1)}},@{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}
```

然后把四个问题**一次问完**，不要连环追问：

> 盘的情况：
> C: 512 GB，已用 430，可用 82
> D: 1 TB，已用 760，可用 240
>
> 要清哪块？另外三件一起回我：
> 1. 想腾出多少？（说"越多越好"也行，我按收益排序）
> 2. 有没有绝对不能动的？（某个项目、游戏、聊天记录、正在用的虚拟机）
> 3. 授权到哪一档：只清缓存 / 也清安装包和重复备份 / 回收站也清 / 允许提权清系统项（旧驱动、组件库）

拿到回答后，用一句话复述成「清理合同」，让他确认或纠正：

> 记下了：清 D 盘，目标 20 GB 以上，不动 SteamLibrary 和 D:\projects\thesis-data，授权到"缓存+安装包"，不提权，回收站留给你自己看。

这一步最常见的错误：他还没说是哪块盘，就开始跑全盘扫描。C 盘 47 万文件 20 秒，
D 盘几十万文件再 20 秒——扫错盘等于白烧两轮，还会把注意力引到错的目录上。

---

## 第 2 步 扫描：把「被什么占了」变成一张能对账的表

### 2.0 先确认工具能跑

```bash
python -V && python scripts/disk_scan.py --help 2>/dev/null || ls scripts/
```

脚本路径相对本 skill 目录。Windows 下别用 PowerShell 现场造扫描器——见「陷阱」。

### 2.1 总账先行

```bash
df -h /c          # 或 /d
```
记下「已用」这个数。后面所有分项都必须能和它对上；对不上就明说差多少。

### 2.2 一次遍历拿全表

```bash
python scripts/disk_scan.py "C:\\" 3 "$TMPDIR/c_scan.json" --big 200
```

- 参数：根路径、报告层数、输出 JSON、`--big` 大文件阈值（MB）。
- Windows 全盘 47 万文件 **13–23 秒**；输出 UTF-8 JSON，用 `execute_code`/`read_file` 读，
  别在 git-bash 里打中文路径表格（乱码）。
- 结果里 `dirs_by_depth` 的每个值都是**该目录的完整大小**（按前缀聚合），不是单层大小。
  `errors` 是读不了的条目数，`total_scanned_gb` 要和 `df` 的已用对比。

读 JSON 时先看总账那一层（depth=1），再按需下钻：

```python
import json
d = json.load(open("c_scan.json", encoding="utf-8"))
for row in d["dirs_by_depth"]["1"][:20]:
    print("%8.2f GB  %s" % (row["gb"], row["path"]))
print("scanned", d["total_scanned_gb"], "GB | root files", d["root_files_gb"],
      "GB | errors", d["errors"])
```

### 2.3 只挖大的

顶层 > 5 GB 的目录各再扫一次，层数 2–3 就停：

```bash
python scripts/disk_scan.py "C:\\Users" 2 "$TMPDIR/users.json"
python scripts/disk_scan.py "C:\\Users\\<name>\\AppData\\Local" 2 "$TMPDIR/local.json"
```

最后**按用户认得出的名字重排**：微信、QQ、WPS、浏览器、NVIDIA、Steam、某个项目目录。
不按深度分层报——他要的是"谁占的"，不是"哪一层"。

### 2.4 专类取证（每类都有专门的判据，不要用大小猜）

| 对象 | 手段 | 判据 |
|---|---|---|
| 回收站 | `python scripts/recycle_dupes.py rb D:\ --out rb.json` | 读 `$I*` 元数据得到原始路径/删除时间/大小；`$R` 多于 `$I` 说明元数据被清，按目录名+子项报 |
| 大压缩包 | `python scripts/recycle_dupes.py zip <包> <目录> --out dup.json` | 叶子名覆盖率 100% 且包远大于目录 → 备份+解压两份 |
| 旧驱动 | `pnputil /enum-drivers` + 注册表 `InfPath`/`DriverVersion` | 版本对上才敢说哪个是残留，见下 |
| 组件库 | `DISM /Online /Cleanup-Image /AnalyzeComponentStore` | 硬链接重复计数，遍历值只是上限 |
| 差值 | `vssadmin list shadowstorage`、`Win32_PageFileUsage` | 要管理员；拿不到就照实说"要提权才能确认" |
| 锁文件 | ACL 组名 + 5 分钟内 mtime + size 是否在涨 | Restart Manager 报"无锁"是假阴性，不能信 |

### 2.5 差值点名，不许抹平

扫到的总量通常**小于**系统报的已用（实测约 166 GB vs 178 GB，差 12 GB）。成因：
无权限目录、`C:\System Volume Information`（还原点/卷影副本）、根目录散文件（`swapfile.sys`）、
NTFS 簇对齐零头。把差值当一条结论报出来并列出候选，说清哪条要提权才能确认。

### 2.6 分四档出方案

| 档 | 内容 | 处理方式 |
|---|---|---|
| **1 纯缓存** | 着色器缓存 DXCache、uv/pip/npm/.gradle、Temp、CachedExtensionVSIXs | 可整目录清，应用自动重建 |
| **2 系统残留** | 旧驱动、WinSxS 组件库 | **必须提权 + 官方工具**（pnputil / DISM），不许手删 |
| **3 确定是垃圾** | 安装包 zip、视频缓存、重复备份包 | 点名后可删 |
| **4 可能是他自己的东西** | 聊天记录、回收站、WPS 插件池、WSL 虚拟盘、云盘下载、书库 | **只报不动**，指路到应用内入口 |

第 4 档绝不能混进建议里。报告格式（每项一行，按 GB 降序）：

```
 #  项目                                    约 GB  是什么              删了会怎样            需提权
 1  AppData\Local\NVIDIA\DXCache              3.2   着色器缓存          首次进游戏略慢，自动重建   否
 2  QQNT\versions\*.zip                       2.8   QQ 安装包           无                    否
 3  DriverStore 里 4 个旧 NVIDIA 驱动包       9.6   旧版驱动            失去这 4 个回滚版本      是
 4  回收站（D:）                              9.6   一年前删掉的旧项目目录 不可恢复             否
```

报告骨架：

```
总账：C: 512 GB，已用 430，可用 82；扫描覆盖 418，差 12 见末尾

一级目录
  C:\Windows            41.2 GB
  C:\Users              96.5 GB
  C:\Program Files      28.7 GB
  ...

下钻（Users）
  AppData\Local        41.2 GB …
  
可清理项
  …（上面那张表）

差值 12 GB：无权限目录 + System Volume Information + swapfile.sys；
其中还原点占用要 vssadmin（管理员）才能确认。

我一项都没动。
```

---

## 第 3 步 让他选：编号、代价、提权都说在前面

不要给"建议全清"这种一句话，也不要只给清单让他自己算。给 **A/B/C 三档 + 编号项**：

```
A 保守：第 1 档缓存全清                     ≈ 14 GB  零风险  不用提权
B 标准：A + 安装包 + 重复备份 + 旧驱动留当前+上一版  ≈ 41 GB  其中 9.6 GB 要管理员
C 彻底：B + 回收站 + 视频缓存                ≈ 52 GB  回收站不可逆

回我编号就行，例如"B，不含回收站"。
```

同时把**提权**讲明白，别让他被 UAC 弹窗吓到：

> 需要管理员的只有三项：pnputil 删旧驱动、DISM 清组件库、vssadmin 查还原点。
> 执行时会弹一次 UAC，你点"是"；不点也能继续，只是这几项腾不出来。
> 驱动默认保留「当前版 + 上一版」当回滚点，要连上一版一起删我另外算差额给你。

还要说清不可逆项：回收站、单独列出的文件、`--apply` 后的缓存目录。

**含糊授权不算授权。** 他说"看着办""你决定"时，把清单重新列一遍，让他至少回一个字母；
他没回就停在扫描结果，什么都不删。

---

## 第 4 步 执行：按清单、先演后删、逐项对账

### 4.1 把授权项写成 plan.json

每一个 target 都必须能追溯到第 2 步的一个编号项。没有编号的路径不许进 plan。

```json
{"targets": [
  {"path": "C:\\Users\\me\\AppData\\Local\\NVIDIA\\DXCache", "mode": "contents", "reason": "#1 shader cache"},
  {"path": "C:\\Users\\me\\AppData\\Local\\Temp",            "mode": "contents", "reason": "#2 temp"},
  {"path": "D:\\Downloads\\old-installer.zip",                "mode": "entry",    "reason": "#5 installer"}
]}
```

- `contents`：清空目录里的条目，**保留目录本体**（应用要重建）。
- `entry`：删掉这个条目本身（文件、安装包，或整个目录）。用整个目录时路径要写到具体那一层，
  绝不能写 `D:\downloads` 这种顶层目录。

### 4.2 先 dry-run

```bash
python scripts/clean_dir.py plan.json --out "$TMPDIR/plan_report.json"
```

它做的事：逐路径过安全闸门（拒绝清单见下）、统计条目数与字节、**不删任何东西**。
把这份清单的摘要给他看一眼（条目数、合计 GB、被拒的路径及原因）。

### 4.3 再执行

```bash
python scripts/clean_dir.py plan.json --apply --min-age-days 1 --out "$TMPDIR/apply.json"
```

- 默认跳过 **5 分钟内改过**的文件（活跃写入），可选 `--skip-active-minutes` 调整。
- 默认**不跟随** junction/symlink：只删链接本身，链接指向的目录原样保留。
- 只读属性的缓存文件会自动去属性重试；被进程占用的文件记为 failure 并跳过，其余照删。
- 一次跑一个目标，`free_delta_gb` 才是这个目标的真实收益；合并成一批就分不清谁释放了多少。

### 4.4 系统项只能走官方工具

```bat
pnputil /enum-drivers
pnputil /delete-driver oem42.inf        :: 不带 /uninstall，不动设备绑定
DISM /Online /Cleanup-Image /StartComponentCleanup
cleanmgr /sageset:1                     :: 让他自己勾，别替他选
```

删驱动前先用注册表 `InfPath` + `Win32_VideoController` 的版本确认"哪个是当前在用的"。
**绝不手删 `FileRepository` 目录**——那是设备绑定的来源，手删会认不出显卡。

### 4.5 对账与交付

```
已执行（授权 1/2/5）
  #1 DXCache            计划 3.2 GB   实删 3.1 GB   失败 3 个（占用）
  #2 Temp               计划 1.8 GB   实删 1.8 GB
  #5 old-installer.zip  计划 1.1 GB   实删 1.1 GB
可用空间：45.2 → 51.3 GB（+6.1）
脚本统计 6.0 GB，差 0.1 GB：簇大小 + 仍被占用的临时文件
未动：第 4 档（回收站、聊天记录）及你标了不能动的东西
```

部分失败就是部分成功，别报成"清完了"。失败项要给出原因和下一步（关掉哪个程序、重启后再清）。

### 4.6 收尾

- 清理临时脚本与中间 JSON（放在 scratch 里，用完删）。
- 如果他常清同一批目录，建议把这些路径固化成 plan.json 模板，下次只跑 dry-run + apply。

---

## 安全红线：这些永不自动删

1. **回收站**——里面常是他自己的文档，不可逆。每次都单独问一句。
2. **`C:\Windows\WinSxS`**——含硬链接，手删会坏系统更新；只用 DISM。
3. **`DriverStore\FileRepository`**——只用 `pnputil /delete-driver`。
4. **`C:\Windows\Installer`**——MSI 缓存，删了卸载/修复就失败。
5. **`pagefile.sys` / `swapfile.sys` / `hiberfil.sys`**——只能挪盘或调小，不能删。
6. **用户桌面/文档/图片/下载的顶层**——要清只能逐文件列名，不做"清空下载文件夹"。
7. **5 分钟内改过或 size 还在涨的文件**——那是活数据，等进程退出后它自己清。
8. **游戏本体 / 创意工坊**——指路 Steam 的卸载与退订，不手删 steamapps。
9. **微信/QQ/邮箱的聊天记录目录**——指路应用内"清理缓存"，不碰 msg 库。
10. **junction / symlink 指向的目标**——只删链接，不穿透。
11. **不在授权名单里的任何路径**，包括同名的另一块盘。
12. **大压缩包**——删前必须做叶子名覆盖比对，确认它是解压版的副本而不是唯一一份。

## 陷阱（都是踩过的）

- **目录大小必须递归算。** `DirEntry.stat().st_size` 对目录永远返回 0，会把 2 GB 的版本目录报成 0 M。
- **别用 PowerShell 的 `EnumerateFiles(..., AllDirectories)` 扫全盘。** 整段包在一个 try/catch 里，
  遇到第一个拒绝访问的目录就整体中断，静默返回零头：实测把 79 GB 的 `C:\Users` 报成 0.05 GB。
  逐目录 `Get-ChildItem -Recurse -Force` 求和数字准，但 D 盘 27 万文件要 247 秒——只当 Python 跑不起来时的兜底。
- **聚合键用"从根算起的前缀"。** 从文件所在目录往上数 N 层的写法会给出下界且层级混杂：
  同一台机器 `C:\Windows` 被报成 18 GB，真值 49 GB。
- **空壳目录不算空间。** Steam 里 0.00 GB 的游戏目录是卸载残留，别拿来凑账。
- **中文路径**：Windows PowerShell 5.1 读无 BOM 的 .ps1 按 GBK 解码，脚本正文只用 ASCII；
  必须写字面量就用码位拼 `$p = 'D:\' + [char]0x4E91 + [char]0x76D8`。结果写 UTF-8 文件再读，别打控制台。
- **Report the delta, don't invent a bucket.** 数字对不上就报差值，编一个"其他 12 GB"是最坏的收尾。
- **不要自己弹 UAC。** 提权前单独问一次，说明弹窗和后果。

## 非 Windows

`df -h`、`du -xhd1 <dir> | sort -h`、`ncdu` 是等价手段，思路不变（总账 → 全表 → 下钻 → 分档）。
`clean_dir.py` 也能跑，但拒绝清单是按 Windows 目录名写的，Linux 下要先确认路径不在 `/etc`、`/usr`、`/var/lib`。

## 参考

- `references/disk-space-forensics.md` — 已知占用大户、判读口径、报告顺序。
- `scripts/disk_scan.py` — 只读扫描，按路径前缀聚合，输出 JSON。
- `scripts/clean_dir.py` — 带安全闸门的清理执行器，dry-run 默认，manifest 驱动。
- `scripts/recycle_dupes.py` — 回收站 `$I` 元数据解析、压缩包覆盖率比对。
