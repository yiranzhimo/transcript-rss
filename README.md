# Transcript RSS

把播客 RSS 和 YouTube 频道转换成可订阅的中文文字稿 RSS。项目由 GitHub
Actions 定期执行，输出静态 HTML、Markdown、VTT 和 RSS，并通过 GitHub
Pages 发布。

## 处理规则

1. 播客优先读取 RSS 中的 `podcast:transcript`。
2. YouTube 优先读取作者字幕，其次读取自动字幕。
3. 没有字幕时，下载音频并使用 `faster-whisper` 转写。
4. 检测到英文文字稿时，通过 OpenAI-compatible 接口翻译成简体中文。
5. 保留原文，并生成中文全文 RSS。

机器识别和翻译可能有误。页面会保留原始节目链接和原文，重要内容应回到原始
音视频核对。

## GitHub 配置

### 1. 修改订阅源

编辑 [`config.yaml`](config.yaml)，删除或替换两个禁用的示例：

```yaml
sources:
  - id: lex-fridman
    type: podcast
    url: https://lexfridman.com/feed/podcast/
    language: en
    enabled: true
    max_items_per_run: 1

  - id: example-channel
    type: youtube
    # 最稳定的是 /channel/UC... 地址；@handle 地址也支持，但发现过程更慢。
    url: https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx
    language: auto
    enabled: true
    max_items_per_run: 1
```

`max_items_per_run: 1` 能避免首次执行时处理整个历史库。后续每次 Action
会继续处理一条尚未发布的内容。

### 2. 配置翻译密钥

在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中添加：

| 类型 | 名称 | 用途 |
|---|---|---|
| Secret | `OPENROUTER_API_KEY` | 英文转简体中文 |
| Variable，可选 | `OPENROUTER_MODEL` | 覆盖 `config.yaml` 中的翻译模型 |

默认调用 `https://openrouter.ai/api/v1/chat/completions`。也可以修改
`translation.api_base` 和 `translation.api_key_env` 接入其他兼容服务。

### 3. 启用 Pages 和 Action 写入

1. 在 **Settings → Pages → Build and deployment** 中选择 **GitHub Actions**。
2. 在 **Settings → Actions → General → Workflow permissions** 中允许
   **Read and write permissions**。
3. 打开 **Actions → Update transcript feeds → Run workflow** 完成第一次执行。

生成后的订阅地址：

```text
https://USERNAME.github.io/REPOSITORY/feed.xml
https://USERNAME.github.io/REPOSITORY/feeds/SOURCE_ID.xml
```

工作流每六小时运行一次。GitHub Pages 地址由 Action 根据仓库所有者和仓库名
自动设置，不依赖 `config.yaml` 中的占位 URL。

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[transcribe,dev]"

export SITE_BASE_URL="http://localhost:8000"
export OPENROUTER_API_KEY="..."

transcript-feed --config config.yaml validate
transcript-feed --config config.yaml sync
python -m http.server 8000 --directory docs
```

## 输出

```text
docs/
├── feed.xml
├── feeds/
│   └── SOURCE_ID.xml
└── items/
    └── ITEM_ID/
        ├── index.html
        ├── original.md
        ├── original.vtt
        ├── zh.md
        ├── zh.txt
        └── zh.vtt
```

RSS 的 `content:encoded` 包含中文正文，并通过 `podcast:transcript` 链接到
中文 VTT。`site.content_mode` 可设为：

- `full`：RSS 内嵌全文。
- `summary`：RSS 内只放节选。
- `link`：RSS 只提供文字稿网页链接。

## 运行限制

- GitHub-hosted Runner 使用 CPU 转写。长节目可能运行较久，因此应限制每次处理
  条数，并优先订阅本身提供字幕的来源。
- `faster-whisper` 模型会缓存在 GitHub Actions cache 中。
- 音频只存在于 Action 临时目录，不会提交到仓库。
- GitHub Pages 通常是公开页面。不要用它公开你无权再发布的完整文字稿；个人
  私密使用应改用带访问控制的存储或私有部署。
- YouTube 页面和字幕接口可能变化，需定期更新 `yt-dlp`。
