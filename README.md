# Codex GPT New Model Cache

让 Codex 在 API key 登录时也能在模型选择器里看到新模型，例如 `gpt-5.5`。

## 解决什么问题

Codex 的模型选择器不是只看 API 是否能调用某个模型，它还会读取本地模型目录。

在 ChatGPT/OAuth 登录时，Codex 通常会从远端刷新模型目录并写入：

```text
~/.codex/models_cache.json
```

但在 API key 登录时，Codex 通常不会主动刷新这份远端模型目录。如果本地没有可用的新鲜缓存，客户端会回退到内置的 `models.json`。当内置目录还没有包含最新模型时，API key 登录的模型选择器就可能看不到新模型。

这个 skill 解决的是：本地模型缓存缺少最新模型元数据。

## 原理

这个 skill 内置一份包含新模型的 `models_cache.json` 模板，并通过脚本写入：

```text
${CODEX_HOME:-~/.codex}/models_cache.json
```

脚本会做几件事：

- 把 `fetched_at` 设置为当前 UTC 时间加 30 天，让 Codex 认为缓存仍然新鲜。
- 保留模板里的模型元数据，包括 `gpt-5.5`。
- 将 `gpt-5.5` 标记为 `supported_in_api: true` 和 `visibility: "list"`。
- 自动匹配 `client_version`，避免版本不一致导致缓存被忽略。
- 覆盖旧缓存前备份为 `models_cache.json.bak`。

`client_version` 的来源优先级：

1. 现有 `~/.codex/models_cache.json` 里的 `client_version`
2. GitHub 上 `openai/codex` 的最新 `rust-v*` release
3. 环境变量 `CODEX_CLIENT_VERSION`
4. 模板里的 `client_version`

## 安装

克隆到 Codex skills 目录：

```bash
mkdir -p ~/.codex/skills
git clone git@github.com:enjin1314/codex-gpt-new-model-cache.git ~/.codex/skills/codex-gpt-new-model-cache
```

如果你的 `CODEX_HOME` 不是 `~/.codex`，请克隆到对应的 skills 目录。

## 使用

运行脚本：

```bash
python3 ~/.codex/skills/codex-gpt-new-model-cache/scripts/write_models_cache.py
```

如果你把 skill 放在其他路径，运行对应路径下的脚本即可：

```bash
python3 /path/to/codex-gpt-new-model-cache/scripts/write_models_cache.py
```

运行成功后会输出写入路径、`fetched_at`、`client_version` 和模型列表。然后重启 Codex，API key 登录的模型选择器里应该可以看到 `gpt-5.5`。

## 自定义 Codex Home

如果你使用自定义 `CODEX_HOME`：

```bash
CODEX_HOME=/path/to/.codex python3 ~/.codex/skills/codex-gpt-new-model-cache/scripts/write_models_cache.py
```

如果你想手动指定缓存版本：

```bash
CODEX_CLIENT_VERSION=0.124.0 python3 ~/.codex/skills/codex-gpt-new-model-cache/scripts/write_models_cache.py
```

脚本会优先使用现有缓存或 GitHub 最新 release，只有它们不可用时才会使用 `CODEX_CLIENT_VERSION`。

## 注意事项

这个 skill 只影响 Codex 的模型选择器缓存，不会绕过任何账号权限。

它不能解决：

- API key 本身没有目标模型权限
- 账号没有目标模型访问资格
- `Computer Use`、Apps、Connectors 等需要 ChatGPT/Codex backend 登录的能力

换句话说，它解决的是“模型列表看不到新模型”，不是“账号获得新模型权限”。

## 文件结构

```text
codex-gpt-new-model-cache/
├── SKILL.md
├── assets/
│   └── models_cache.template.json
└── scripts/
    └── write_models_cache.py
```

