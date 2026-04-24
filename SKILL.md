---
name: codex-gpt-new-model-cache
description: 当用户想让 Codex API-key/API 登录显示 GPT-5.5 或其他新 GPT 模型时使用；writes ~/.codex/models_cache.json with a prepared model catalog cache.
metadata:
  short-description: 让 Codex API 登录显示 GPT-5.5
version: 0.2.0
---

# Codex GPT 新模型缓存

当用户要求让 Codex API-key 登录也能看到 GPT-5.5、刷新本地 Codex 模型缓存，或写入包含 GPT-5.5 的 `~/.codex/models_cache.json` 时，使用这个 skill。

## 使用方式

运行内置脚本：

```bash
python3 /Users/用户路径/Documents/toolAgents/.codex/skills/codex-gpt-new-model-cache/scripts/write_models_cache.py
```

脚本会读取 `assets/models_cache.template.json` 模板，并写入 `${CODEX_HOME:-~/.codex}/models_cache.json`。

## 行为

- 将 `fetched_at` 设置为当前 UTC 时间加 30 天。
- 设置 `client_version` 时，优先使用现有缓存，其次读取 GitHub 最新 `rust-v*` release，再尝试 `CODEX_CLIENT_VERSION`，最后使用模板值。
- 保留模板里的 `etag` 和模型元数据。
- 包含 `gpt-5.5`，并设置为 `supported_in_api: true`、`visibility: "list"`。
- 必要时自动创建 Codex home 目录。
- 覆盖前会把现有缓存备份为 `models_cache.json.bak`。

## 注意事项

Codex 仍会按登录方式过滤模型。API-key 登录只会显示 `supported_in_api: true` 的模型；`visibility: "hide"` 的模型仍不会出现在普通模型选择器里。

不要用 `codex --version` 作为 `client_version`；它返回的是 CLI 版本，可能不同于 Codex 桌面客户端/app-server 使用的模型缓存版本。

GitHub release 查询使用 `https://api.github.com/repos/openai/codex/releases/latest`，并从 `tag_name` 中去掉 `rust-v` 前缀。
