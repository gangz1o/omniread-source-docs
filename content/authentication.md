# 登录规范

返回 [规范入口](README.md)。v1 有两条不同路径：新服务使用原生令牌登录；既有网站可使用网页登录。二者不能混在同一源中。

## 1. 原生登录声明

在普通规则书源顶层增加：

```json
{
  "omnireadLogin": {
    "version": 1,
    "type": "password",
    "loginUrl": "https://library.example/account/login",
    "sessionUrl": "https://library.example/account/session"
  }
}
```

| 字段 | 要求 |
| --- | --- |
| `version` | 必填整数，必须为 `1`；未知版本拒绝导入 |
| `type` | 必填，`password` 或 `apiKey` |
| `loginUrl` | 必填完整 HTTPS 地址，无查询、片段和 URL 用户名/密码 |
| `sessionUrl` | 必填完整 HTTPS 地址，同样无查询、片段和用户信息 |

两个接口必须与 `bookSourceUrl` 同源：协议、主机、有效端口一致。HTTPS 默认端口视为 443。不能用兄弟域名、子域名、另一端口或 HTTP 代替。声明最大 4 KiB，不支持远程动态登录表单。

原生登录 APP 表单固定为“账号 + 密码”或“API 密钥”，并显示凭据提交主机。不存在额外字段、任意 HTML、用户脚本和自动执行按钮。`loginUrl` 等旧式字段不得同时出现；专用聚合适配也不能与此声明混用。错误声明直接阻止导入，不静默降级为匿名请求。

## 2. 账号密码交换

```http
POST /account/login
Content-Type: application/json
Accept: application/json

{"username":"reader","password":"user-entered-password"}
```

账号去除首尾空白，密码保持原样；各字段 UTF-8 长度不超过 4096 字节且不能为空。服务端必须支持 JSON 字符串正确转义，不能要求客户端拼接密码、加密脚本或固定设备标识。

API 密钥模式只改变请求体：

```json
{"apiKey":"user-entered-api-key"}
```

密钥去除首尾空白。原始账号密码/API 密钥只用于这次交换，不作为书源定义或运行期脚本变量保存。

## 3. 登录响应

成功必须返回 HTTP 200：

```json
{"accessToken":"opaque-example-token","expiresIn":3600}
```

- `accessToken`：非空字符串，最多 8192 个 ASCII 字节，仅允许可见非空格 ASCII（33–126），不得包含换行。
- `expiresIn`：JSON 整数，1–31536000 秒。APP 以接收响应时刻计算过期时间。建议使用较短期限并支持再次登录。
- 响应最大 64 KiB；不需要包装 `code`、`data`。APP 不解析 `refreshToken`、`user`、`message` 或任意动态字段。
- 凭据错误返回 401 或 403。限流返回 429；服务异常返回 5xx。不得返回“200 + HTML 登录页面”或“200 + 错误文本”。
- APP 显示固定中文错误，不将服务器响应原样展示或记录，避免回显凭据。
- 登录和会话请求不跟随重定向，不复用浏览器 Cookie，不缓存响应。接口必须直接返回最终结果。

## 4. 阅读请求鉴权

APP 在同一书源的搜索、发现列表、详情、目录和章节 HTTP 请求上附加：

```http
Authorization: Bearer opaque-example-token
```

声明原生登录的源按“需登录”处理，未登录时不发起这些受保护请求。分类列表本身可以由静态 `exploreUrl` 生成。

只允许对声明的同源 HTTPS API 发送令牌，不跟随重定向，不附加共享 Cookie。规则中的 `header.Authorization` 不能覆盖原生令牌。没有把令牌插入 URL、脚本或 JSON 模板的占位符。

**资源下载是另一条链路。** 封面、漫画图片、音频、短剧视频和整书下载链接应由服务器返回可直接访问的 URL 或短期签名 URL；APP 不向这些资源转发原生令牌。也不向 `java.ajax/post` 注入令牌。不要把登录令牌改放资源查询参数来规避这个边界。

## 5. 会话检查与失效

```http
GET /account/session
Authorization: Bearer opaque-example-token
Accept: application/json
```

| 响应 / 状态 | APP 行为 |
| --- | --- |
| 200 或 204 | 已验证；响应体不参与登录状态判断 |
| 401 | 会话失效，清除对应本地令牌并提示重新登录 |
| 403 | 无访问权限，保留凭据，不能据此断言全局会话过期 |
| 超时、离线、429、5xx | 保留凭据，显示暂时无法验证，允许重试 |
| 本地过期 | 不再发送该令牌，重新登录 |

普通受保护 API 也必须用 401 表示令牌失效；“HTTP 200 + 自定义错误码”不会触发原生会话失效处理。书籍权限不足用 403。不要以注销所有用户令牌回应普通内容权限失败。

令牌保存在 Keychain，与本地书源 ID、影响规则执行的定义指纹绑定，启动/再次使用书源时恢复。改变执行规则、地址或登录声明会要求重新登录，不能将旧令牌迁往新服务。

并发规则：退出或取消登录后，迟到的响应不能重新保存登录；旧请求的 401 不能清除后来建立的新会话；阅读器隔离上下文共享同一原生会话撤销状态。

## 6. 退出与刷新

“退出登录”删除本地保存的令牌、清理运行期会话并取消尚未完成的登录提交。**v1 的退出是本地退出，不调用服务端撤销接口。** 服务端应通过令牌期限和自己的账号管理提供远程撤销；不能把 APP 本地退出视为已经远端注销。

v1 不保存原始密码、不自动重新提交密码、不实现 refresh token。过期后用户重新输入凭据。这是此版本的接口边界，不应在 `jsLib` 中自行补一套密码缓存。

## 7. 旧式网页登录

无 `omnireadLogin` 的源可保留现有网页登录方式：

```json
{
  "bookSourceUrl":"https://library.example/",
  "enabledCookieJar":true,
  "loginUrl":"https://library.example/login"
}
```

当前解析器将 `loginUrl` 视为“支持登录”的声明，优先从 `bookSourceUrl` 取得可加载的入口。**不能承诺会直接打开 `/login`，请确保首页能够进入登录页面。** 用户在 APP 内网页完成登录，APP 同步受作用域限制的 Cookie。

`loginCheckJs` 不作为通用会话校验脚本执行；`loginUi` 只有已识别的专用协议可能转换成原生字段。需要稳定的自建服务原生登录时应使用前述 `omnireadLogin`。

网页登录兼容性需在实际站点测试：验证码、跨站单点登录、特殊 Cookie、浏览器挑战和服务策略可能不兼容。通用规范不保证绕过这些要求，也不将网页 JS 功能映射成原生能力。
