---
name: dsh-wechat-bridge
description: "Use when 把 DSH（DeepSeek Harness）接到微信做远程控制，或修 iLink/ClawBot 桥接。agent 主导配置，人只负责 key、扫码、点授权。"
version: 1.0.0
author: Northseacaviar
license: MIT
metadata:
  hermes:
    tags: [dsh, deepseek-harness, wechat, ilink, clawbot, bridge, remote-control, windows]
---

# DSH 接微信：扫码 → headless → 守护

你在 Windows 上配置一个常驻程序：微信 ClawBot 收到消息 → 本机 DSH 执行 → 结果发回微信。

**由你完成全部工作。** 人只在三个时刻介入：提供 API key、扫码、点权限弹窗。

## 何时用

- 要把 DSH 从「人在电脑前用」变成「手机微信里发指令」。
- 已有的桥接坏了：二维码不出、消息不回、重启丢了消息。
- 想评估「DSH 能不能远程控制」这条路可不可行。

不适用：只想要单个结果推送（用企业微信 webhook 或飞书就够）；要边看边改的交互式编码（headless 没有这个形态，用远程桌面）。

## 环境事实

已确认，直接用，不要重新探测：

- DSH 全局安装：`%APPDATA%\npm\node_modules\@deepseek-ai\dsh`，入口 `lib\bin.js`
- 调用方式：`node <入口> headless -` —— 任务从 **stdin** 读；答案在 stdout，模型思考过程在 stderr
- 凭据：headless profile **默认禁用 credentials 插件**，需在 profile patch 里打开（见步骤 5）；打开后直接复用图形界面已配好的 key，**不需要再设环境变量**
- 微信侧 SDK：`https://github.com/openilink/openilink-sdk-python`（**PyPI 上没有这个包**）
- 安装命令：`python -m pip install -e ".[qrcode]"` —— qrcode 是可选依赖，不显式装会在导入 `print_qrcode` 时 ImportError
- Python 必须 ≥3.10，Node ≥18
- 微信版本：iOS ≥8.0.70 / 安卓 ≥8.0.69 / 鸿蒙 ≥8.0.16.51，且「我 → 设置 → 插件」里必须有 ClawBot

## 交付物

| 文件 | 说明 |
|---|---|
| `D:\dsh-bridge\bridge.py` | 主程序，全文见最后一节 |
| `D:\dsh-bridge\start.bat` | 循环守护，全文见最后一节 |
| Startup 快捷方式 | 指向 start.bat |

## 执行步骤

**1. 验证环境**

```cmd
python -V
node -v
git --version
```

任一不满足（Python <3.10 或 Node <18）→ **停下报告，不要自己装运行时**。

**2. 装 SDK**

```cmd
cd /d D:\
git clone https://github.com/openilink/openilink-sdk-python.git
cd openilink-sdk-python
python -m pip install -e ".[qrcode]"
python -c "import openilink, qrcode; print('ok')"
```

最后一条必须打印 `ok`。失败处理：
- clone 超时 → 换代理域名，**下回来是 HTML 不算成功**
- `Microsoft Visual C++ 14.0 required` → 先 `python -m pip install --upgrade pip`，再不行报告人
- `requires-python >=3.10` → 人装的 Python 太老，报告人

**3. 写 `bridge.py`**（全文见最后一节）

**4. 写 `start.bat`**（全文见最后一节）

**5. 启用凭据插件**（不然后面一定报 MISSING_CREDENTIAL）

DSH 的 headless profile **默认把凭据插件关了**（`disabled: true`），所以哪怕图形界面里已经配过 key，headless 也读不到。改 `~/.dsh/profiles/headless/cordis.patch.yml`：

```yaml
- id: credentials
  disabled: false
```

验证配置生效：

```cmd
node %APPDATA%\npm\node_modules\@deepseek-ai\dsh\lib\bin.js headless --dump-config
```

输出里 `- id: credentials` 那段的 `disabled` 必须是 `false`。

再**不带任何环境变量**跑一次：

```cmd
node %APPDATA%\npm\node_modules\@deepseek-ai\dsh\lib\bin.js headless "只回答两个字：收到"
```

- **能输出** → 凭据复用成功，跳过下面的兜底
- **仍报 `MISSING_CREDENTIAL`** → 这台机器从没配过 key。在 `dsh web` 的 Models 页面填一次（之后所有 profile 共享）；临时应急才用 `set DEEPSEEK_API_KEY=sk-xxx`

**6. 配自启**：把 `start.bat` 的快捷方式放进 `shell:startup`

**7. 首次运行并要人扫码**

```cmd
cd /d D:\dsh-bridge
python bridge.py
```

终端出现二维码后**停下**，说「请用微信扫这个码」。不要自己往下走。

**8. 填白名单**

人扫码并发一条消息后，读 `D:\dsh-bridge\bridge.log` 里被拒绝的 `uid`，填进 `bridge.py` 的 `ALLOW`，重启程序。

**9. 自检**（见下节）

## 必须停下来找人的三个时刻

| 时刻 | 你要说的话 | 为什么不能自己解决 |
|---|---|---|
| 缺 API key | 「需要一个 DeepSeek API key」 | 无法猜测或生成 |
| 二维码出现 | 「请用微信扫码」 | 只有人的手机能扫 |
| 权限弹窗 | 「需要点同意，我在等」 | 沙箱授权必须人批 |

遇到这行报错：

```
Error: SetNamedSecurityInfoW failed (Win32 5): grantWrite(D:\...)
```

**这不是故障，是权限未授权。** 告诉人「需要点同意」，等回复。反复出现就让人把会话切到 full access。

## 自检（全过才算完成）

```cmd
python -m py_compile D:\dsh-bridge\bridge.py
type D:\dsh-bridge\bridge.log
tasklist /FI "IMAGENAME eq python.exe"
```

然后请人做三件事、把结果回报给你：

1. 微信发「这个目录里有几个文件」→ 有具体回答
2. 用另一个微信号发消息 → 无响应，且 `bridge.log` 出现「拒绝非白名单」
3. `taskkill /IM python.exe /F` → 5 秒内自动重启，再发微信仍有回复

**任何一条不过，不要说完成了。**

## 陷阱

**一、不要用 `pythonw`。** 它 `sys.stdout` 是 `None`，print 被静默丢弃、异常堆栈也看不到。用 `python` + 窗口最小化。

**二、任务必须走 stdin（`headless -`），不要拼进命令行。** Windows 上 `.cmd` 会把参数交给 cmd.exe 解释，微信消息里一个 `x" & echo 1 > f & "` 就能在本机落文件。走 stdin 后这个面完全消失。

**三、`cursor.txt` 是增量游标，重启会补跑停机期间到达的消息。** 这是 SDK 的断点续传设计，不是 bug。人昨晚发的「删掉测试目录」，今早开机就会执行。要清就删文件。

**四、`ALLOW` 是空集合时全部拒绝**，连人自己也被拒。必须填 `user_id` 才放行。

**五、同一个 bot 只能跑一个实例。** 两个进程同时长轮询会互相偷消息，谁都答不全。代码里的 `bridge.lock` 挡这个。

**六、stderr 里是模型的思考过程**（如 `Hmm, keep it concise...`），不是错误。只在 stdout 为空时才回退取 stderr。

**七、iLink 只能私聊**，群消息基本收不到事件。

**八、`~/.dsh/.credentials.yaml` 里有 key 不等于 headless 能用。** headless profile 把 credentials 插件设成 `disabled: true`，图形界面配的凭据它读不到。不要去复制 key 到环境变量，改一行 patch 就行。

## 边界

- **能做**：一次性任务。例「修复 app.py 的报错」「跑测试并总结失败项」
- **做不了**：交互式编程。headless 每次新会话，不记得上一条指令
- **若「我 → 设置 → 插件」里没有 ClawBot**：停下报告，不要硬试。替代方案是飞书，桥接代码只换收发那 10 行
- **不要装 DSH 的第三方微信插件**（那批最高 4 star，要求交出微信登录态）

## 代码全文

### `D:\dsh-bridge\bridge.py`

```python
# -*- coding: utf-8 -*-
import os, sys, json, time, queue, logging, subprocess, threading
from pathlib import Path
from openilink import Client, LoginCallbacks, MonitorOptions, extract_text, print_qrcode

BASE = Path(r"D:\dsh-bridge"); BASE.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=str(BASE / "bridge.log"), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bridge")

CRED   = BASE / "cred.json"
CURSOR = BASE / "cursor.txt"
LOCK   = BASE / "bridge.lock"

WORKDIR = r"D:\dsh-work"     # DSH 干活的目录，按实际项目改
TIMEOUT = 1800
ALLOW   = set()              # 填 user_id，例：{"xxx@im.wechat"}；空 = 全部拒绝

def single_instance():
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().strip())
            os.kill(pid, 0)
            print(f"已有实例 pid={pid} 在跑"); sys.exit(1)
        except (ValueError, OSError):
            pass
    LOCK.write_text(str(os.getpid()))
    import atexit
    atexit.register(lambda: LOCK.unlink(missing_ok=True))

def dsh_js() -> str:
    r = subprocess.run(["npm.cmd", "root", "-g"], capture_output=True, text=True)
    root = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
    p = Path(root) / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
    if not p.exists():
        raise FileNotFoundError(f"找不到 {p}；先 npm install -g @deepseek-ai/dsh")
    return str(p)

DSH_JS = dsh_js()
single_instance()

HINT = """你是通过微信远程接活的编程助手。规则：
1. 先判断再动手。明确的小改动直接做；涉及结构调整、技术选型、改多个文件，先分析；
   信息不够（没说哪个文件、没贴报错），先问，不要猜。
2. 有取舍就给方案，等人拍板。停下来给至少两个方案，每个写清：怎么做、代价是什么、
   你倾向哪个。写完就停。只有用户明确说"你看着办"才自己定。
3. 不许假装做完。没跑过就说没跑过。改文件前先读现状。报错原样贴出来。
4. 微信里说话要短。先结论后依据。超过 10 行的代码写进文件，不要贴聊天里。
5. 不确定就问。宁可回"这几点我没法确定"，也不要编一个像样的答案。"""

def run_dsh(task: str) -> str:
    if not os.path.isdir(WORKDIR):
        return f"工作目录不存在：{WORKDIR}（改 WORKDIR 或建目录）"
    p = subprocess.Popen(
        ["node", DSH_JS, "headless", "-"],     # "-" = 任务从 stdin 读，不进命令行
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=WORKDIR, text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    try:
        out, err = p.communicate(input=HINT + "\n\n----\n\n用户任务：\n" + task, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        try: p.communicate(timeout=10)
        except Exception: pass
        return f"超时 {TIMEOUT}s，已强制终止进程树"
    if p.returncode != 0:
        log.warning("dsh rc=%s stderr=%s", p.returncode, (err or "")[-500:])
    out = (out or "").strip()
    return out or (err or "").strip()[-1500:] or f"（无输出，exit={p.returncode}）"

cred = json.loads(CRED.read_text(encoding="utf-8")) if CRED.exists() else {}
_kw = {"token": cred.get("token", "")}
if cred.get("base_url"):
    _kw["base_url"] = cred["base_url"]
client = Client(**_kw)
if not cred.get("token"):
    r = client.login_with_qr(callbacks=LoginCallbacks(on_qrcode=print_qrcode))
    if not r.connected:
        sys.exit(f"登录失败: {r.message}")
    CRED.write_text(json.dumps({"token": r.bot_token,
                                "base_url": getattr(r, "base_url", "")}), encoding="utf-8")

def reply(uid: str, text: str, n: int = 1200):
    for i in range(0, max(len(text), 1), n):
        try:
            client.push(uid, text[i:i + n] or "（空）")
        except Exception as e:
            log.error("push 失败: %s", e); break
        time.sleep(0.6)

Q: "queue.Queue" = queue.Queue()
def worker():
    while True:
        uid, task = Q.get()
        try: reply(uid, run_dsh(task))
        except Exception as e:
            log.exception("worker"); reply(uid, f"执行异常：{e}")
        finally: Q.task_done()
threading.Thread(target=worker, daemon=True).start()

def handler(msg):
    if "BOT" in str(getattr(msg, "message_type", "")).upper():
        return
    uid = getattr(msg, "from_user_id", None)
    text = extract_text(msg).strip()
    if not uid or not text: return
    if uid not in ALLOW:
        log.warning("拒绝非白名单 uid=%s", uid); return
    ahead = Q.qsize()
    reply(uid, f"收到，排队中…（前面 {ahead} 个）" if ahead else "收到，开始跑…")
    Q.put((uid, text))

log.info("bridge 启动 pid=%s workdir=%s", os.getpid(), WORKDIR)
client.monitor(handler, opts=MonitorOptions(
    initial_buf=CURSOR.read_text(encoding="utf-8") if CURSOR.exists() else "",
    on_buf_update=lambda b: CURSOR.write_text(b, encoding="utf-8"),
    on_error=lambda e: log.warning("monitor err: %s", e),
    on_session_expired=lambda: log.error("会话过期，删 cred.json 重扫"),
))
```

### `D:\dsh-bridge\start.bat`

```bat
@echo off
cd /d D:\dsh-bridge

:loop
python "D:\dsh-bridge\bridge.py" >> "D:\dsh-bridge\console.log" 2>&1
echo [%date% %time%] bridge 退出 rc=%errorlevel%，5 秒后重启 >> "D:\dsh-bridge\watch.log"
ping -n 6 127.0.0.1 >nul
goto loop
```
