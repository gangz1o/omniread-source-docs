# 云书阁书源开发规范 v1.0

状态：仓库实现与开发者联调规范。日期：2026-09-28。

面向书源作者、自建内容服务维护者。以本目录示例和回归测试为验收基线。**通用原生登录和显式短剧类型为本次新增能力；不能假定已发布的 App Store 版本支持它。** 发布时须在发行说明标注首次支持的 APP 版本与构建号；当前工程版本号不作为已上线证明。

本规范中的“必须”是 v1 发布要求，“建议”是推荐做法，“兼容”表示已有引擎可处理但不作为新书源的首选写法。导入器有历史容错，能导入不等于符合规范，也不等于站点可访问。

## 1. 阅读路径

1. [快速上手与字段参考](#2-快速上手)：创建可导入 JSON。
2. [请求与规则](rules.md)：搜索、详情、目录、正文及脚本边界。
3. [内容格式](media.md)：小说、漫画、有声书、短剧及资源请求。
4. [登录规范](authentication.md)：原生账号密码/API 密钥和网页登录。
5. [自建服务与演示服务](server.md)：可直接实现的接口及本地联调。
6. [校验与发布](validation.md)：校验工具、验收清单、错误排查。
7. [JSON Schema](source.schema.json)：编辑器字段校验。
8. [维护说明](implementation.md)：源码对应、版本边界及验证记录。

## 2. 快速上手

复制 [novel.json](examples/novel.json)，将 `https://demo.omniread.invalid` 替换为自己的服务地址，保持端点和返回字段与规则一致。这个域名是占位符，**没有在线演示服务**。需要本地跑通时按 [server.md](server.md) 启动配套服务。

六个完整示例：

| 文件 | 媒介 | 认证 |
| --- | --- | --- |
| [novel.json](examples/novel.json) | 小说 | 无 |
| [comic.json](examples/comic.json) | 漫画 | 无 |
| [audio.json](examples/audio.json) | 有声书 | 无 |
| [video.json](examples/video.json) | 短剧 | 无 |
| [account.json](examples/account.json) | 小说 | 原生账号密码 |
| [key.json](examples/key.json) | 小说 | 原生 API 密钥 |

作者工作流：准备响应 → 写规则 → 静态检查 → APP 导入 → 完整阅读测试 → 发布 JSON 和支持版本。云书阁负责 UI、阅读与本地状态；作者负责自己的端点、解析规则、内容和账号服务。

```bash
swift run --package-path MetadataScraper booksource-check docs/book-source/examples/novel.json
```

APP 支持粘贴 JSON、文件和 URL 导入。批量导入及可用书源数量受 APP 当前权益限制；开发者规范不会绕过产品限制。单次文件/响应上限 32 MiB，最多 5000 个源。建议一个文件一个源，合集才使用数组。

## 3. 文件与身份约定

- UTF-8 严格 JSON，不含注释、尾逗号或可执行文件；对象字段使用本规范大小写。
- 顶层为一个对象，或非空对象数组。不要包装成 `{ "sources": [...] }`。
- `bookSourceUrl` 是**导入去重身份和相对地址基准**。相同字符串会更新同一源，保留本地 ID 和启用状态。
- 不同媒介需要独立源时，使用不同稳定路径，例如 `https://host.example/novel/` 和 `/comic/`。
- 必须使用稳定的 HTTP(S) 地址，不放查询参数、用户名、密码、片段、`##` 或请求选项后缀。原生登录源必须 HTTPS。
- 域名、端口或路径变化会改变身份；重命名 `bookSourceName` 不改变导入去重身份。
- 详情与章节 URL 应稳定；访问签名放在实际媒体资源地址中，不要把临时签名作为书籍/章节标识。
- 不要分享密码、Cookie、访问令牌，或将它们硬编码进 `header`、脚本、URL、注释。
- 发布作者仅应提供自己有权提供或用户有权访问的内容。规范不提供共享账号或内容目录。

## 4. 顶层字段

| 字段 | 类型 / 默认 | 含义与要求 |
| --- | --- | --- |
| `bookSourceName` | string，必填 | 可读名称，不能空白 |
| `bookSourceUrl` | string，必填 | 稳定身份和基础地址，见上一节 |
| `bookSourceType` | integer，默认 0 | `0` 小说，`1` 有声书，`2` 漫画；v1 必须只用这三值 |
| `omnireadMediaType` | string，可选 | 云书阁扩展：`"video"` 表示短剧，须配合 `bookSourceType: 0`；不是阅读格式中的数字类型 |
| `bookSourceVersion` | string，可选 | 作者的发布版本，建议 `1.0.0`；不是 APP 版本或引擎版本 |
| `bookSourceGroup` | string，可选 | 分组标签 |
| `bookSourceComment` | string，可选 | 作者、内容说明、变更说明、联系渠道；不作为执行配置 |
| `enabled` | boolean，默认 true | 首次导入的启用状态；更新时保留用户开关 |
| `charset` | string，可选 | 响应编码提示，建议 UTF-8；旧站点可用 `gbk` |
| `header` | string，可选 | **包含 JSON 对象的字符串**，或支持的脚本；不是嵌套 JSON 对象 |
| `concurrentRate` | string，可选 | 最小请求间隔（毫秒），或 `次数/毫秒`，如 `3/1000` |
| `searchUrl` | string，v1 必填 | 搜索请求模板 |
| `ruleSearch` | object，v1 必填 | 搜索结果提取 |
| `exploreUrl` | string，可选 | 分类列表或返回分类的脚本 |
| `ruleExplore` | object，可选 | 发现列表提取；建议显式提供 |
| `ruleBookInfo` | object，建议提供 | 详情字段与目录地址 |
| `ruleToc` | object，v1 必填 | 章节目录提取 |
| `ruleContent` | object，v1 必填 | 当前章节内容提取 |
| `jsLib` | string，可选 | 纯 JavaScript 辅助函数；见脚本支持表 |
| `omnireadLogin` | object，可选 | 本规范新增的原生认证声明；见登录规范 |
| `enabledCookieJar` | boolean，默认 false | 旧式网页登录/Cookie 书源；不用于原生令牌认证 |
| `loginUrl` | string，可选 | 旧式登录能力声明；**不保证其字符串地址原样打开** |
| `loginUi` / `loginCheckJs` | 历史兼容 | 不属于通用原生登录接口，不能靠这些字段创建任意表单或执行登录脚本 |

未列出的阅读生态字段不作支持承诺：解析器可能忽略它们；导出也不保证保留。不要往 APP 内部持久化 JSON 添加 `id`、`nativeLogin`、`compatibilityVersion` 等内部字段来代替公开导入格式。

通用原生登录源不能与专用聚合服务适配脚本混用。`omnireadLogin` 不能与 `loginUrl`、`loginUi`、`loginCheckJs` 同时声明；应选择一种认证方式。

## 5. 规则对象字段

以下所有规则值均为字符串。JSONPath 以当前阶段的对象为根，不一定是整个响应。

| 对象 | 字段 | 求值位置 |
| --- | --- | --- |
| `ruleSearch` / `ruleExplore` | `bookList` | 整个列表响应，返回书籍节点列表 |
| 同上 | `name`、`bookUrl` | 每个书籍节点，必填；缺少值的条目可能被跳过 |
| 同上 | `author`、`kind`、`intro`、`coverUrl`、`lastChapter` | 每个书籍节点，可选 |
| `ruleBookInfo` | `init` | 可选，先选择详情子节点作为后续详情规则的根 |
| 同上 | `name`、`author`、`kind`、`intro`、`coverUrl`、`lastChapter` | 详情根节点，可选 |
| 同上 | `tocUrl` | 目录地址；省略时以详情地址作为目录 |
| 同上 | `downloadUrls` | 可选整书下载地址；兼容别名 `downloadUrl`，新源使用复数名 |
| `ruleToc` | `chapterList` | 整个目录响应，返回有序章节列表 |
| 同上 | `chapterName`、`chapterUrl` | 每个章节节点，v1 必填 |
| 同上 | `nextTocUrl` | **整个目录响应**，下一页地址，可省略 |
| `ruleContent` | `content` | 整个章节响应，提取正文或媒体资源列表，必填 |
| 同上 | `nextContentUrl` | 整个章节响应，同一章节的下一页，可选 |
| 同上 | `replaceRegex` | 小说正文的正则净化规则，可选 |

不要假定 `isVip`、`isPay`、`isVolume`、`wordCount`、`updateTime`、自定义按钮或筛选器会自动产生 APP 功能。v1 没有这些通用字段协议。

## 6. 版本与更新

本规范版本、作者的 `bookSourceVersion`、APP 发行版本三者独立。v1 不新增虚假的 `minAppVersion` 或 `capabilities` 解析功能；支持版本目前由作者在发布说明中列出。

重新导入同一 `bookSourceUrl` 即更新规则；不会按版本字符串阻止回退。普通第三方源不具备通用自动订阅更新协议。现有聚合源专用更新路由、`omnireadUpdateMetadata` 属于内部兼容，不作为新源作者入口。

原生登录令牌与影响执行的书源字段绑定。改变名称、请求头、规则、脚本或登录声明后，旧凭据可能需要重新登录；只改作者版本/说明不会改变此绑定。不要为了“保留登录”伪造旧定义。

## 7. v1 能力边界

已支持：规则导入与导出、搜索/发现/详情/目录/章节、四类媒介、基本分页、CSS/JSONPath/XPath、受支持 JavaScript、原生令牌登录、旧式网页登录。

不包含：任意动态原生表单、执行导入的登录 UI 脚本、OAuth/PKCE、自动 token 刷新、原生验证码、多账号同时登录同一源、跨域共享令牌、任意 HTTP header 的媒体转发、远端阅读进度同步、通用书源市场或服务发现。音色、多线路切换虽有部分已有服务支持，暂不作为此 v1 的通用扩展承诺。短剧以单集视频资源接入已有播放器，不新增根 Tab。

自建服务可以按示例 API 返回 JSON，再通过规则接入，**不需要等待另一种“标准 API 书源”导入格式**。v1 的线格式仍然只有这里的 JSON 规则书源。
