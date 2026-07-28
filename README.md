# Transcript RSS

把播客 RSS、YouTube 频道和 Bilibili UP 主转换成可订阅的中文文字稿 RSS。项目由 GitHub
Actions 定期执行，输出静态 HTML、Markdown、VTT 和 RSS，并通过 GitHub
Pages 发布。

## 处理规则

1. 播客优先读取 RSS 中的 `podcast:transcript`。
2. YouTube 和 Bilibili 优先读取平台字幕，其次读取自动字幕。
3. 没有字幕时，下载音频并使用 `faster-whisper` 转写。
4. 检测到英文文字稿时，通过 OpenAI-compatible 接口翻译成简体中文。
5. 保留原文，并生成中文全文 RSS。

机器识别和翻译可能有误。页面会保留原始节目链接和原文，重要内容应回到原始
音视频核对。

### Whisper 转录性能

默认使用 `small + CPU + int8`，并启用批处理以兼顾中文识别质量和速度：

```yaml
transcription:
  model: small
  device: cpu
  compute_type: int8
  batch_size: 8
  beam_size: 1
  cpu_threads: 4
  log_progress: true
```

`batch_size: 0` 可关闭批处理。增大批大小会提高内存占用；减小模型或
`beam_size` 通常更快，但可能降低嘈杂语音、多人对话和专有名词的识别质量。
修改参数后应先用有代表性的节目比较速度和文字准确度。

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

  - id: example-bilibili
    type: bilibili
    # 使用 UP 主空间地址，例如 https://space.bilibili.com/123456
    url: https://space.bilibili.com/123456
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
| Secret，可选 | `YOUTUBE_PROXY` | YouTube 请求使用的 HTTP/SOCKS 代理 |
| Secret，可选 | `YOUTUBE_COOKIES_B64` | Netscape cookies 文件的 Base64 内容 |

默认调用 `https://openrouter.ai/api/v1/chat/completions`。也可以修改
`translation.api_base` 和 `translation.api_key_env` 接入其他兼容服务。

### YouTube 的机器人验证

工作流默认包含三层无账号处理：

1. Deno 运行 YouTube 的 JavaScript challenge solver。
2. 安装 `yt-dlp-ejs`。
3. 启动 `bgutil-ytdlp-pot-provider` 服务，为每个视频生成 PO Token。

这能减少 `Sign in to confirm you’re not a bot`，但不能保证绕过 YouTube
对 GitHub 数据中心 IP 的限制。如果仍被拦截，优先配置 `YOUTUBE_PROXY`。

只有私人、低频使用且代理仍无法解决时，才考虑 `YOUTUBE_COOKIES_B64`。生成方法：

```bash
base64 < youtube-cookies.txt | tr -d '\n'
```

把输出保存为 GitHub Actions Secret `YOUTUBE_COOKIES_B64`。cookies 文件必须是
Mozilla/Netscape 格式。不要使用主 Google 账号；YouTube 可能轮换 cookies，
账号也存在临时或永久限制风险。cookies 只会写入 Runner 临时目录，不会提交。

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

# macOS；其他平台安装 Deno 2.x 或 Node 22+
brew install deno

# 可选：本地启动 PO Token provider
docker run --rm --init -p 4416:4416 \
  brainicism/bgutil-ytdlp-pot-provider:1.3.1

export SITE_BASE_URL="http://localhost:8000"
export OPENROUTER_API_KEY="..."
export YOUTUBE_POT_PROVIDER_URL="http://127.0.0.1:4416"

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
