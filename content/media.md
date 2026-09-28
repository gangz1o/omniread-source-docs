# 章节与资源格式

返回 [规范入口](README.md)。四种媒介共用搜索、详情和目录规则，差异在 `bookSourceType` 及 `ruleContent.content` 的最终值。

## 1. 小说（0）

接口返回：

```json
{"text":"第一章 云间来信\n\n窗外的雨停了。\n书桌上留着一封信。"}
```

规则：`{"content":"$.text"}`。也可返回 HTML，使用 `@css:#content@html`；APP 清理标签并提取段落。不要把整页导航、广告、登录错误或一整本书当作一个章节返回。

正文应为可读文本，使用换行表达段落。需要同一章分页时声明 `nextContentUrl`，每章最多 10 个响应页。`replaceRegex` 用于净化，不用于复杂协议解密。

小说插图已有 HTML 提取能力，但神评论、音色、聚合平台自定义正文元数据不在本规范通用承诺内。

## 2. 漫画（2）

接口返回有序的 URL 字符串数组：

```json
{"pages":["/assets/page-1.png","/assets/page-2.png"]}
```

规则：`{"content":"$.pages[*]"}`（或 `$.pages`）。也可提取 HTML 的 `img@src`，结果按行排列；数组/行顺序即阅读顺序。

需要逐资源请求头时，返回对象并显式序列化：

```json
{
  "pages":[
    {"url":"https://cdn.example/page-1.jpg","headers":{"Referer":"https://library.example/"}},
    {"url":"https://cdn.example/page-2.jpg","headers":{"Referer":"https://library.example/"}}
  ]
}
```

规则：`{"content":"@js:JSON.stringify(result.pages)"}`。不要用 `$.pages` 期待自动保留对象中的 headers。

每章最多 2000 个图片资源，单份原始图片列表最多 4 MiB，嵌套收集深度最多 6。相同最终 URL 去重，保留首次顺序。图片应分辨率合理、独立可访问，避免一张极高的整本拼图；APP 只按邻近页面预加载，不保证同时解码全部图片。

## 3. 有声书（1）

最简单的接口：

```json
{"audio":"https://cdn.example/chapter-1.mp3"}
```

规则：`{"content":"$.audio"}`。若需要 headers，使用 `{"audio":{"url":"…","headers":{"Referer":"…"}}}`，规则改为 `@js:JSON.stringify(result.audio)`。

解析器兼容 `url`、`src`、`audio`、`audioUrl`、`audioURL`、`audio_url`、`playUrl`、`playURL`、`play_url`、`content` 等资源键，以及 `data`、`urls`、`audios`、`tracks`、`list`、`qualities` 集合键。新源使用 `url` / `headers` 即可。

每章最多提取 8 个候选资源，字符串原始值最多 64 KiB，嵌套最多 6 层。**数组不表示多段音频顺序拼接，也不承诺提供清晰度选择器。** v1 建议每章一个可播放资源，多段拆为目录章节。

建议提供 iOS 系统播放器可直接播放的 MP3、M4A 或合适的 HLS。URL 解析成功不代表编码可播放；作者须验证启动、暂停、拖动、后台播放和过期链接恢复。没有任意私有加密流/DRM 解码接口。

## 4. 短剧（云书阁扩展）

顶层必须声明：

```json
{"bookSourceType":0,"omnireadMediaType":"video"}
```

不要自行使用 `bookSourceType: 3` 或靠 `bookSourceGroup: "短剧"` 选择播放器。`omnireadMediaType` 是云书阁扩展，当前只接受 `video`；与 `bookSourceType` 的 1/2 冲突或填未知值时拒绝导入。其他阅读客户端可能忽略此扩展，不保证跨客户端短剧兼容。

搜索结果对应一部剧，详情描述整部剧，目录一项对应一集，按集序排列。目录的 `chapterName` 写“第 1 集 来信”等可读名称，`chapterUrl` 指向该集的资源解析接口。

```json
{"video":"https://cdn.example/episode-1.mp4"}
```

规则 `{"content":"$.video"}`。带请求头时可返回 `{"video":{"url":"…","headers":{"Referer":"…"}}}`，规则用 `@js:JSON.stringify(result.video)`。也兼容小型 `<video src="…">` / `<source src="…">` 片段和 `videoUrl`、`playUrl`、`m3u8` 等别名；新服务只需采用 `url`。

推荐系统播放器能直接播放的 MP4（例如 H.264/AAC）或 HLS。实际容器/编码支持须设备验证。单集最多提取 8 个候选 URL、原始字符串最多 64 KiB、嵌套最多 6 层；新源每集提供一个地址。多个 URL 不等于分段合并，也不是自动生成线路/清晰度选择器的协议。

MP4 服务应支持字节 Range。HLS 的清单、分片及所需密钥应各自可访问；不支持为所有 CDN 请求任意注入原生登录令牌，也不提供私有 DRM 解密扩展。资源白名单、签名时效规则与下面的通用约定相同。

短剧复用已有详情、剧集目录、播放器和观看记录；不增加新根 Tab。v1 不包含剧集字幕字段、清晰度标签协议、广告动作、互动剧情或弹幕协议。作者须验证首集/末集、切集、暂停、定位、横竖屏、失效链接和观看进度恢复。演示文件见 [video.json](examples/video.json)，配套服务返回自制 2 秒测试视频。

## 5. 通用资源规则

- HTTP(S) URL；拒绝 `file:`、`javascript:`、URL 内用户名/密码等输入。脚本不能用资源字段读取本机文件。
- 支持相对路径，以当前章节响应地址为基准。推荐绝对 HTTPS 或 `/` 开头的路径。
- 资源 headers 仅保留 `Accept`、`Accept-Language`、`Origin`、`Range`、`Referer`、`User-Agent`；不转发 `Cookie`、`Authorization` 或自定义认证头。
- 最多保留 16 个候选 header 项；值最多 2048 字节，禁止换行。不要依赖超限后的保留顺序。
- 兼容 `https://cdn.example/a.mp3,{"headers":{"Referer":"https://library.example/"}}`，新 API 推荐对象格式。
- 覆盖图、漫画、音频、直接下载地址应由服务端授予有限时效访问。不要将账号密码或会话令牌直接塞进 URL。
- v1 没有通用 `expiresAt` 媒体刷新协议。签名应覆盖正常加载/播放时长；失效时用户可能需要重新打开章节以再次解析，不能宣称无缝续签。
- 音频服务器建议正确支持 Range、Content-Type 和内容长度，以便系统播放器定位；漫画响应应是图片本身，不是网页查看器。
- 离线下载使用 APP 已有功能和实际支持的资源类型；书源声明不会自动增加一种新的离线格式。

## 6. 限制摘要

| 对象 | 当前上限 | 处理原则 |
| --- | --- | --- |
| 单次源导入 | 32 MiB / 5000 源 | 超限拒绝 |
| 原生登录声明 | 4 KiB | 超限拒绝 |
| 原生登录/会话响应 | 64 KiB | 超限失败 |
| APP 规则页面响应 | 16 MiB | 流式上限；不同引擎调用方可能更低 |
| 目录分页 | 100 页 | 完整校验模式拒绝未完成目录 |
| 单章正文分页 | 10 页 | 作者不得依赖超限内容被继续加载 |
| 单章漫画图片 | 2000 | 截取上限内资源 |
| 单章音频 / 单集视频候选 | 8 | 截取上限内资源 |

上限是保护边界，不是推荐数据规模；分发前应远低于上限并用实际设备验收。
