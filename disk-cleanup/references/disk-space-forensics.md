# Windows 磁盘占用：已知大户与判读口径

## 判读口径（先看这条，决定数字可不可信）

- **目录 size 含硬链接会重复计数。** `C:\Windows\WinSxS` 里大量条目是指向 `System32` 的硬链接，
  按文件遍历得到的 11 GB 是口径上限，真值要用 `DISM /Online /Cleanup-Image /AnalyzeComponentStore`（需管理员）。
- **差值大小本身就是诊断信号。** 实测 D 盘扫到约 189 GB、系统报已用 188 GB，只剩零头；差到 GB 级就说明
  有无权限目录没进去。差值来自：无权限目录、`C:\System Volume Information`（还原点/卷影副本，`vssadmin`
  非管理员直接拒绝）、根目录散文件（`swapfile.sys`，`Get-CimInstance Win32_PageFileUsage` 看真实位置）、
  NTFS 簇对齐零头。**差值单独报，不并进总数。**
- **回收站别预设它是小的。** 实测一块数据盘 9.6 GB / 约 30 万个文件，全来自一次整目录删除的 conda 环境
  （`pkgs` 5.39 + `Library` 2.43 + `Lib` 1.63，删于一年多前）。报数，别猜。
- 顶层 `C:\System.sav`、`C:\hp` 是 OEM 出厂镜像残留：既不是系统垃圾，也不是用户数据，单独标注。

## 已知大户（典型值，用于对照，不是清单模板）

| 位置 | 典型大小 | 性质 | 处置 |
|---|---|---|---|
| `Windows\System32\DriverStore\FileRepository` | 15–25 GB | 显卡驱动多版本并存：NVIDIA `nvhm.inf_amd64_*` 每版本 1.7–2.6 GB，常见 6 份 | `pnputil /delete-driver`，留当前+上一版 |
| `Windows\WinSxS` | 10 GB+ | 组件库，含硬链接 | `DISM /StartComponentCleanup` |
| `Windows\Installer` | 1–3 GB | MSI 缓存 | 不动 |
| `Windows\SystemApps`、`assembly`、`Microsoft.NET` | 各 0.8–2.3 GB | 系统运行时 | 不动 |
| `AppData\Local\NVIDIA\DXCache`、`AppData\LocalLow\NVIDIA\PerDriverVersion` | 各 1–4 GB | 着色器缓存 | 可清 |
| `AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_*\LocalState\ext4.vhdx` | 数 GB | WSL 虚拟盘，只增不减 | `wsl --manage <distro> --resize` 或在发行版内清 |
| `AppData\Local\Temp` | 1–3 GB | 常有单个 GB 级 `.tmp` 残留 | 可清 |
| `AppData\Local\{uv\cache, pip\cache, npm-cache}`、`~/.cache`、`~/.gradle` | 合计 3–6 GB | 包管理器缓存 | 可清，会重下 |
| `AppData\Roaming\Tencent\xwechat` + `~/xwechat_files/*/msg` | 5–10 GB | 微信 4.x 图片/视频/附件 | 应用内清理 |
| `Documents\WeChat Files\*\BackupFiles` | 1–3 GB | 手机聊天备份，多为旧机残留 | 确认后删 |
| `Program Files (x86)\Tencent\QQNT\versions\*.zip` | 2–3 GB | 安装包 | 可删 |
| `AppData\Roaming\Kingsoft\wps\addons\pool` | 1–3 GB | WPS 插件池 | 应用内清 |
| `Videos\bilibili` 等播放器缓存 | 3–5 GB | 视频缓存 | 可清 |
| `AppData\Roaming\Code\CachedExtensionVSIXs` | 1 GB | VSCode 扩展离线包 | 可删 |

## 非系统盘

| 位置 | 典型大小 | 性质 | 判读 |
|---|---|---|---|
| `SteamLibrary\steamapps\common\<游戏>` | 0.05–10 GB | 游戏本体 | 0.00 GB 的是卸载残留空壳，不算账 |
| `SteamLibrary\steamapps\workshop\content\<appid>` | 5–25 GB | 创意工坊（431960 = Wallpaper Engine、1477070 = Depersonalization、646570 = Slay the Spire） | 按 appid 报对应游戏名，否则用户不知道退订谁 |
| `360MoveData\Users\<user>\Documents` | 10–20 GB | 360 搬家产物：`WeChat Files`、`Tencent Files`、录屏 | 第 4 档，不动 |
| 云盘下载 / 下载目录 | 10–15 GB | 分卷包（`.z01`）与解压目录并存、旧安装包 | 分卷+解压通常是两份 |
| 资料目录 + 同名 `.zip` | 15–30 GB | 备份包与解压版 | 先做叶子名覆盖比对 |
| 根目录 `pagefile.sys` | ≈ 物理内存 | 页面文件 | 只能挪盘或调小 |

## 系统项需要管理员的三个原因

- **驱动**：`DriverStore` 受 ACL 保护，且 `pnputil` 要改驱动库索引；手删目录会让设备认不出。
- **组件库**：`WinSxS` 由 CBS 管理，DISM 通过服务接口做事，直接删会破坏后续更新。
- **还原点**：`vssadmin` 要卷影复制服务权限，普通用户连查询都被拒。

## 报告顺序

总账（已用/可用）→ 一级目录全表（含 <1 GB 的也列，让账目闭合）→ 最大的那级下钻 2–3 层、
按用户认得出的软件名重排 → 可清理项按 GB 降序、每项带风险与提权标记 → 未查明的差值及成因 →
一句「没动任何文件」。

## 纪律

- 只读阶段一个文件都不动；用户对「查一下」的理解是不动文件。
- 提权（`vssadmin`、`DISM`、`pnputil`）之前单独问一次，不自己弹 UAC。
- 删除只对点名项执行；同一块盘上的同类目录不在授权内。
