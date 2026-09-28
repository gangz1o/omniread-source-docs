# 自建服务接入与演示服务

返回 [规范入口](README.md)。这里给出可直接实现的响应约定；这些路径是**示例选择**，不是 APP 硬编码路由。已有后端可用规则映射自己的路径和字段。

## 1. API 列表

以小说 `/novel` 为例：

| 请求 | 返回 | 规则位置 |
| --- | --- | --- |
| `GET /novel/search?q=关键词&page=1` | `{"books":[...]}` | `searchUrl` + `ruleSearch` |
| `GET /novel/explore?page=1` | `{"books":[...]}` | `exploreUrl` + `ruleExplore` |
| `GET /novel/books/demo` | 书籍详情对象 | `ruleBookInfo` |
| `GET /novel/books/demo/chapters` | `{"chapters":[...],"next":""}` | `ruleToc` |
| `GET /novel/chapters/1` | `{"text":"正文"}` | `ruleContent` |

书籍对象：

```json
{
  "title":"云间小记",
  "author":"演示作者",
  "tags":["原创"],
  "intro":"用于联调的原创内容。",
  "cover":"/assets/page-1.png",
  "url":"/novel/books/demo",
  "toc":"/novel/books/demo/chapters",
  "lastChapter":"第二章 晴天"
}
```

目录对象：

```json
{
  "chapters":[
    {"title":"第一章 来信","url":"/novel/chapters/1"},
    {"title":"第二章 晴天","url":"/novel/chapters/2"}
  ],
  "next":""
}
```

分页末尾应返回空列表 / 空 next，不要永久重复上一页。`title` 和资源 URL 不可缺失；author、intro、cover 等可选，不要用 `"null"` 字符串表示缺失。

漫画、有声书、短剧使用相同模型，章节分别返回 `pages` 字符串数组、`audio` 字符串、`video` 字符串；细节见 [media.md](media.md)。原生登录服务再实现 [authentication.md](authentication.md) 的两个接口。

响应建议 UTF-8 JSON，正确设置 `Content-Type: application/json`。错误使用实际 HTTP 状态：401 登录过期、403 无权限、404 不存在、429 限流、5xx 服务异常；不要返回被规则误识别为正文的登录页。

## 2. 运行配套演示

仅依赖 Python 3 标准库，全部内容为自有测试文本、程序生成图片、提示音和自制测试视频。示例包含两章，不访问第三方内容站点。

仓库根目录执行：

```bash
python3 docs/book-source/demo/server.py
```

开发机访问 `http://127.0.0.1:8765/sources.json` 得到替换好地址的四种匿名书源。默认只监听本机，HTTP 模式不会导出原生登录源。

模拟器可使用开发机回环地址；真机不能用 `127.0.0.1` 指代电脑。需要局域网联调时使用电脑局域网 IP 并显式绑定：

```bash
python3 docs/book-source/demo/server.py --bind 0.0.0.0 --base-url http://192.168.1.20:8765
```

将地址替换为自己的局域网地址，并允许 APP 的本地网络访问。HTTP 能否连接仍取决于客户端网络策略；正式源使用 HTTPS。

## 3. 登录联调

必须使用设备信任的 HTTPS 证书。可以把一个自己控制的 HTTPS 反向代理指向本机演示服务：

```bash
python3 docs/book-source/demo/server.py --base-url https://your-demo.example
```

服务仍监听本机 HTTP，代理负责 TLS；生成的六个书源全部使用外部 HTTPS 根地址。`your-demo.example` 也是占位符，需换成自己的地址。不要在 APP 中关闭证书校验来跑示例。

也可直接使用证书启动 TLS：

```bash
python3 docs/book-source/demo/server.py --port 8765 --base-url https://your-demo.example:8765 --tls-cert /path/fullchain.pem --tls-key /path/private-key.pem
```

演示凭据（仅为这个演示程序的固定测试值）：

- 账号模式：账号 `demo`，密码 `demo-password`。
- API 密钥模式：`demo-api-key`。

`GET /sources.json` 返回六个可导入源。APP 按当前权益允许导入一个或多个。原生源在现有“书源设置”中登录；登录后搜索“云间”，打开详情、目录和第一章；退出后再次发起请求应提示登录。

演示服务每次签发随机令牌，1 小时过期，内存最多保存 100 个未过期会话，重启服务即撤销全部会话。媒体示例提供 Range 响应。有声示例是 2 秒提示音，不是语音朗读。

这是联调 fixture，**不是可直接部署的生产账号系统**：没有注册、密码数据库、验证码、访问日志或持久化会话。生产实现应使用自己的认证与内容授权体系，仅对外满足本协议。

## 4. 对接已有服务

先映射业务数据，再映射认证：

1. 确定稳定的书籍/章节地址和分页顺序。
2. 用 JSONPath/CSS 提取现有响应；字段不同不需要改 APP。
3. 若已有登录接口不符合 v1，可增加服务端适配端点，把账号或密钥换成具有过期时间的 Bearer 令牌。
4. 受保护内容 API 保持与源同源；跨域 CDN 通过独立签名 URL 返回资源。
5. 不支持的认证流程（如 OAuth 和原生验证码）不要伪装成 v1，保留网页登录或等待独立协议扩展。
