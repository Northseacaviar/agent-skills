# README / Release / CHANGELOG 模板

填的时候守三条：只写陌生人需要知道的、命令能直接复制、数字给真值。

## 工具型（CLI、脚本、单文件插件）

```markdown
# <名字> v1.2.0

一句话说清它做什么，再补一句适用场景。

## 安装

    <一条命令，或"下载 <文件> 放到任意目录">

## 使用

    <最小可用示例>
    <带参数的示例>

输出长什么样：

    <真实输出片段>

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--out` | `out.json` | 输出路径 |

## 已知限制

- <两条以内，写事实不写道歉>

## 许可

MIT © [@账号名](https://github.com/账号名)
```

## 库型（包、SDK）

```markdown
# <包名> v1.2.0

一句话定位。支持 <语言/平台版本>。

## 安装

    pip install <包名>        # 或 npm i / cargo add

## 快速开始

```python
from pkg import thing

thing.run("input")
```

## API

### `thing.run(path, *, strict=False)`

做什么。`strict=True` 时行为有何不同。返回什么。

## 测试

    pytest -q

## 许可

MIT © [@账号名](https://github.com/账号名)
```

## Release notes

```markdown
## v1.2.0

**新增**
- 支持把结果导出为 CSV（`--format csv`）

**修复**
- 空目录时不再抛异常

**升级**
- 无需改动配置；旧版 `--json` 参数仍可用

完整变更：https://github.com/<owner>/<repo>/compare/v1.1.0...v1.2.0
```

## CHANGELOG（Keep a Changelog 简化版）

```markdown
# Changelog

## [Unreleased]

## [1.2.0] - 2026-10-27
### Added
- CSV 导出

### Fixed
- 空目录崩溃

## [1.1.0] - 2026-10-10
### Changed
- 配置文件从 ini 换成 toml（不兼容，需迁移）
```

版本号在这里与 `package.json` / 代码常量 / README 首行保持一致；tag 用 `v1.2.0`，
正文不带 `v`。
