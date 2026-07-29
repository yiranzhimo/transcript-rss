# Transcript RSS

把播客 RSS、YouTube 频道和 Bilibili UP 主转换成可订阅的中文文字稿 RSS。项目由 GitHub
Actions 定期执行，输出静态 HTML、Markdown、VTT 和 RSS，并通过 GitHub
Pages 发布。

## 处理规则

1. 播客优先读取 RSS 中的 `podcast:transcript`；没有字幕时下载音频并用
   `faster-whisper` 转写。
2. YouTube 和 Bilibili **不转录**：GitHub Actions 的共享 IP 几乎必定被两个
   平台的风控拦截（YouTube 返回 "Sign in to confirm you're not a bot"，
   Bilibili 返回 HTTP 412），逐视频请求字幕或音频已被证明不可行。因此这两类
   来源只做"发现更新"——用来源自带的标题 + 简介生成条目、附上原始视频链接，
   方便你自己去网页上看/转录，不下载音频也不调用平台字幕接口。
3. 检测到英文内容时，通过 OpenAI-compatible 接口翻译成简体中文（播客的完整
   文字稿、YouTube/Bilibili 的标题与简介都会翻译）。
4. 保留原文，并生成中文全文 RSS。

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
    # 推荐直接用官方 Atom feed（不经过 yt-dlp，几乎不会被拦）：
    # https://www.youtube.com/feeds/videos.xml?channel_id=UCxxxxxxxxxxxxxxxxxxxxxx
    # 找 channel_id：打开频道任意视频页 → 查看网页源码搜索 "channelId"，
    # 或者本地运行 `yt-dlp --flat-playlist --playlist-items 1 -J <频道地址> | jq .channel_id`。
    # 也支持 @handle 地址，但发现过程会退化成 yt-dlp 抓取，更慢也更容易被限流。
    url: https://www.youtube.com/feeds/videos.xml?channel_id=UCxxxxxxxxxxxxxxxxxxxxxx
    language: auto
    enabled: true
    max_items_per_run: 1

  - id: example-bilibili
    type: bilibili
    # 使用 UP 主空间地址，例如 https://space.bilibili.com/123456
    # 没有官方 RSS，发现新视频仍然通过 yt-dlp 抓取空间页，偶尔会被风控拦截
    # 一次；失败的来源会在下次运行自动重试。
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
| Secret，可选 | `YOUTUBE_PROXY` | yt-dlp 发现阶段（Bilibili 空间页、YouTube `@handle` 频道列表）使用的 HTTP/SOCKS 代理 |

默认调用 `https://openrouter.ai/api/v1/chat/completions`。也可以修改
`translation.api_base` 和 `translation.api_key_env` 接入其他兼容服务。

YouTube/Bilibili 不再逐视频请求字幕或音频（见「处理规则」），所以不需要
YouTube cookies、PO Token、Deno 之类的反爬配置。`YOUTUBE_PROXY` 只在
「发现新视频」这一步生效——主要是给经常被风控拦截的 Bilibili 空间页用的；
YouTube 只要用官方 Atom feed（见上面的 `example-channel`）几乎用不上代理。

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

工作流每十二小时运行一次。GitHub Pages 地址由 Action 根据仓库所有者和仓库名
自动设置，不依赖 `config.yaml` 中的占位 URL。

### 并行处理

工作流会为每个启用的订阅源建立独立 matrix job，并通过 `max-parallel: 4`
限制为最多四个 Runner 同时执行。各 job 只上传该来源的状态片段和新文字稿；
最后一个 publish job 统一合并状态、重建 RSS、提交仓库并部署 Pages，避免多个
Runner 同时修改 `state.json` 或推送 Git。

单个来源失败不会覆盖其他来源的结果。汇总日志会列出没有成功上传 artifact
的来源；单个来源 job 的最长运行时间为三小时。

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
- YouTube/Bilibili 的「发现新视频」仍然依赖 `yt-dlp`（Bilibili 空间页、
  YouTube `@handle` 频道列表），页面结构变化时需要定期更新 `yt-dlp`。
