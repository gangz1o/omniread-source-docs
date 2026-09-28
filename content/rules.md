# 请求与规则参考

返回 [规范入口](README.md)。下列语法基于当前云书阁引擎，不能据此推断阅读 APP 的所有能力都兼容。

## 1. 请求模板

```json
{
  "searchUrl": "/novel/search?q={{key}}&page={{page}}",
  "header": "{\"Accept\":\"application/json\",\"User-Agent\":\"MyLibrary/1.0\"}"
}
```

- `{{key}}` 是按字符集百分号编码后的关键词；不要再套一层 URL 编码。
- `{{page}}` 首次为 1；后端从 0 开始时可用 `{{page-1}}`。
- 搜索与发现翻页由 APP 请求下一页。最后一页返回空列表，不要重复返回第一页。
- 历史 `searchKey`/`searchPage` 字面替换受兼容；新源优先花括号写法。
- 模板中普通 `{{...}}` 表达式可以求值；脚本中的 `key` 则是原始关键词。
- 搜索/发现相对地址以 `bookSourceUrl` 为基准。提取出来的详情、目录和章节地址通常以当前响应地址为基准；建议从 `/` 开始或使用完整 HTTPS URL。

### POST 搜索

搜索和发现模板支持 `url,{选项}` 后缀。`body` 必须为字符串；`headers` 必须为字符串值字典。

```json
{
  "searchUrl": "/search,{\"method\":\"POST\",\"body\":\"q={{key}}&page={{page}}\",\"headers\":{\"Content-Type\":\"application/x-www-form-urlencoded\"}}"
}
```

选项包括 `method`、`body`、`headers`、`charset`。默认 GET；有 body 且没声明 Content-Type 时默认为表单。JSON body 应通过脚本 `JSON.stringify` 安全生成并显式设置 JSON Content-Type，不能将用户关键词直接拼接进 JSON 字符串。

**这个选项处理不适用于所有 URL 字段。** 当前详情/目录/章节页面抓取以 GET 为主，URL 后缀中的 method/body/headers 不会作为通用请求配置执行。图片/音频资源的 `,{"headers":{...}}` 是另一层资源解析能力，见内容规范。

不要依赖未列出的 `webView`、`js`、`retry` 等 URL 选项。

## 2. JSONPath（新建 API 书源优先使用）

响应：

```json
{"books":[{"title":"云间小记","author":"演示作者","url":"/novel/books/demo"}]}
```

规则：

```json
{"bookList":"$.books[*]","name":"$.title","author":"$.author","bookUrl":"$.url"}
```

| 写法 | 作用 |
| --- | --- |
| `$.data.title` | 对象字段 |
| `$.books[0]` / `$.books[*]` | 下标 / 全部元素 |
| `$..title` | 递归查找字段 |
| `$.books[0:5]` | 切片，右边界不包含，可带步长 |
| `$.books[0,2]` / `$['a','b']` | 联合选择 |
| `$.books[?(@.enabled)]` | 存在性过滤 |
| `$.books[?(@.type == 'novel')]` | 单条件比较，支持 `== != > < >= <=` |
| `@json:$.books[*]` | 兼容前缀写法 |

不承诺支持完整 JSONPath 标准，尤其是脚本下标和嵌套过滤器。复杂转换使用短小的 JavaScript，不要拼接多层未经测试的语法。

**字符串字段规则不会自动序列化对象。** `$.pages` 对字符串数组可得到逐行 URL；如果数组包含 `{url, headers}` 对象，应使用 `@js:JSON.stringify(result.pages)`。详情的 `init: "$.data"` 会改变后续根节点，之后用 `$.title`，而不是再写 `$.data.title`。

## 3. HTML / CSS / XPath

```json
{
  "bookList":"@css:.book",
  "name":"@css:h2@text",
  "author":"@css:.author@text",
  "bookUrl":"@css:a@href",
  "coverUrl":"@css:img@src"
}
```

列表规则选择节点；字段规则在该节点内执行。字段提取常用 `@text`、`@html` 和属性名 `@href`、`@src`、`@data-src`。正文按需求用 `@html` 保留段落标签供清洗，或提取多个段落的文字。

兼容阅读默认选择语法，例如 `class.bookbox@tag.h4@text`、`id.content@text`、`tag.a@href`。支持索引/列表/区间等兼容写法，但新源优先标准 CSS 与明确的测试响应。

XPath 示例：`@XPath://h1/text()`、`//div[@id='chapters']/a/@href`。它作用于静态响应 HTML，不会运行网页 JavaScript 来生成 DOM。

## 4. 组合与替换

| 写法 | 用途 |
| --- | --- |
| `a||b` | 第一条有结果的规则 |
| `a&&b` | 字符串提取结果按换行拼接 |
| `a%%b` | 两组结果交错合并 |
| `-$.chapters[*]` | 列表逆序，例如倒序目录 |
| `规则##正则##替换` | 字符串后处理 |
| `规则##正则` | 删除匹配内容 |
| 尾部 `###` | 只处理首次匹配的兼容形式 |
| `@put:{"bookID":"$.id"}` / `@get:{bookID}` | 书源运行期变量写入/替换 |

不同阶段的列表与字符串求值路径不完全相同；不要将字符串连接规则当作所有列表字段的通用语法。新源用 JSON 返回有序数组最稳妥。

正文净化示例：`"replaceRegex":"##广告：[^\\n]*"`。JSON 中反斜杠须转义。避免过宽正则误删正文，也不要使用可能长时间回溯的表达式。

## 5. 分页与排序

- 目录 `nextTocUrl` 从整页响应提取，可返回一个下一页地址或换行分隔的多个目录页地址。
- 下一页不存在时省略字段或给空字符串；不要返回 `"null"`、当前页、上一页。
- 目录最多抓取 100 页，并检测已访问 URL。完整目录校验在达到上限且仍有下一页时失败。
- 正文 `nextContentUrl` 只用于**同一章**分页，最多 10 页；不得指向下一章，否则正文会串章。
- 目录按服务返回顺序阅读。列表需自然正序；重复章节 URL、空章节名、分页重叠应在服务端修正。
- 搜索、发现、目录和正文分页是四种不同流程，不要相互替代。

## 6. 发现分类

静态格式：

```json
{"exploreUrl":"推荐::/novel/explore?sort=recommended&page={{page}}\n最新::/novel/explore?sort=recent&page={{page}}"}
```

也可放一个 **JSON 数组的字符串**，或脚本返回同样数组：

```json
{"exploreUrl":"[{\"title\":\"推荐\",\"url\":\"/novel/explore?page={{page}}\",\"type\":\"url\"}]"}
```

分类项使用 `title`（兼容 `name`）、`url`，可选 `type: "url"`。登录、充值、公告、书源设置等工具项会被过滤；这里用于内容分类，不是菜单注入入口。发现结果字段优先显式提供 `ruleExplore`。

## 7. JavaScript 支持边界

运行环境为 JavaScriptCore，规则采用 `@js:表达式/脚本` 或 `<js>...</js>`。`jsLib` 可声明辅助函数；不能依赖脚本上下文永久存在、顶层副作用只执行一次或请求串行。

常用变量：`result`（当前 JSON 对象、HTML 字符串或前序提取结果）、`baseUrl`、`key`、`page`、`source.bookSourceUrl`、`source.bookSourceName`。`book`、`chapter` 仅含调用方提供的上下文，不保证都有书名、当前章节下标等值。

```json
{"content":"@js:JSON.stringify(result.pages)"}
```

可用桥接以以下清单为边界，`java` 只是兼容名称，不是 Java 虚拟机：

| 方法 | 说明 |
| --- | --- |
| `java.put(key,value)` / `java.get(key)` | 有容量限制的运行期字符串变量；不是持久化数据库或凭据库 |
| `java.getString(rule)` / `getStringList(rule)` | 对当前节点提取字符串 / 字符串列表 |
| `java.getElement(rule)` / `getElements(rule)` | 序列化节点字符串 / 数组，不是可任意调用的 Java DOM 对象 |
| `java.ajax(url)` | 同步受限网络请求；失败不等价于浏览器行为 |
| `java.post(url,body,headersJSON)` | POST，第三参数为请求头 JSON 字符串 |
| `base64Encode(s)`、`base64Decode(s)`、`base64DecodeToByteArray(s)` | 均挂在 `java` 下 |
| `md5Encode(s)`、`md5Encode16(s)`、`HMacHex(data,algorithm,key)` | 摘要/签名兼容；不作为凭据存储方式 |
| `aesBase64DecodeToString(data,key,transformation,iv)` | 受支持的 AES 解码；不是任意加密工厂 |
| `encodeURI(s)`、`htmlFormat(s)`、`toNumChapter(s)`、`t2s(s)`、`s2t(s)` | 编码、清洗、章节数字、繁简转换 |
| `hexDecodeToString(s)`、`hexEncodeToString(s)`、`hexDecodeToByteArray(s)` | Hex 转换 |
| `timeFormat(milliseconds)`、`timeFormatUTC(milliseconds,format,hoursOffset)`、`randomUUID()` | 时间与随机标识 |
| `deviceID()`、`androidId()`、`getWebViewUA()` | 兼容值；不是 Android 系统能力或硬件身份 |
| `getCookie(url,name)` | 受作用域限制的 Cookie 读取 |
| `log(s)`、`toast(s)`、`longToast(s)` | 兼容占位，不保证打印或显示提示 |

`source.getVariable()` / `setVariable(string)` 可访问非敏感运行期配置。`source.getLoginInfo()` / `getLoginInfoMap()` / `getLoginHeader()` 仅对已有专用登录适配有意义，**不会返回 `omnireadLogin` 的密码或令牌**。

旧 Cookie 模式可使用 `cookie.getString(url)`、`getCookie(url)`、`getKey(url,name)`、`setCookie(url,value)`、`removeCookie(url)`，受源域名和原生保护凭据边界约束，不代表任意站点 Cookie 访问。

不支持通用 `cache` 对象、`Packages`/Rhino Java 互操作、浏览器 DOM、`window`、网页 WebView 执行、文件读写、任意 `java.*` 方法。不要依赖 `java.webView`、`java.startBrowserAwait`、`java.ajaxAll`、`java.connect`、`java.head`、`java.setContent` 等未实现 API。个别专用适配的例外不属于公开协议。

原生登录源的受保护请求必须走 `searchUrl` / 详情 / 目录 / 内容正常抓取流程。`java.ajax/post` 不附加原生访问令牌；脚本不可读取令牌自行签名。需要不同鉴权方式的服务应在服务端适配 v1。
