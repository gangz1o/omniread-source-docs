# NAS / WebDAV 接入

有 NAS 的用户有两种接入方式。**如果只是自己读 NAS 里的文件，先用 APP 自带的 WebDAV；如果希望在“书源”中搜索、发现和按章节阅读，再运行本页的适配服务。**

| 你想做什么 | 选择 |
| --- | --- |
| 浏览 NAS 文件夹，把文件作为自己的书库使用 | APP 原生 WebDAV 连接，无需编写书源 |
| 将 NAS 小说整理成一个可搜索、可导入的书源 | 运行 WebDAV → 书源适配服务 |
| 把适配方法分享给其他 NAS 用户 | 分享示例代码和配置模板，各自连接自己的 NAS |

## 1. 直接连接 NAS

在「藏书阁」的设置入口打开 WebDAV 连接管理，选择「添加 WebDAV 连接」。填写服务器地址、HTTP/HTTPS、端口、书库路径、用户名和密码，测试连接后保存，再选择要使用的书库文件夹。

例如 WebDAV 完整地址是 `https://nas.example:5006/Books/Novels/`，则填写：

| 表单字段 | 示例 |
| --- | --- |
| 名称 | 家里的 NAS |
| 地址 | `nas.example` |
| 连接方式 | HTTPS |
| 端口 | `5006` |
| 路径 | `/Books/Novels/` |
| 用户名 / 密码 | NAS 上为此目录设置的只读账号 |

地址、端口和路径以你的 NAS 实际设置为准，示例不是可访问服务。手机必须能访问 NAS：同一局域网、自己的 VPN，或已配置的远程入口。`127.0.0.1` 在手机上指手机自身。APP 的 WebDAV 凭据保存在设备 Keychain 中。

这种方式进入 APP 的私人书库，不会自动生成一个 JSON 书源，也不需要本页桥接服务。具体文件格式以当前 APP 支持情况为准。

## 2. 为什么需要适配服务

WebDAV 返回文件和目录；规则书源需要搜索结果、书籍详情、章节目录及章节正文。仅将 WebDAV 根地址填进 `bookSourceUrl`，不会自动扫描目录、解析 TXT 或生成目录规则。

```text
NAS 的指定小说目录
  ↓ PROPFIND 列目录 / GET 读取 TXT
你自己的 WebDAV 适配服务
  ↓ 搜索、详情、目录、正文 JSON API
云书阁书源 → 小说阅读器
```

WebDAV 的目录枚举使用 PROPFIND 和多状态 XML 响应；示例按 [RFC 4918](https://www.rfc-editor.org/rfc/rfc4918.html#section-9.1) 处理 `Depth: 1`。适配器在自己的网络内访问 NAS，APP 只访问适配器的 HTTPS 地址。

**本页提供可运行的 TXT 小说示例。** EPUB、PDF、漫画压缩包、有声书和视频不由这个示例转换；它们需要各自的内容提取/资源授权实现，不能改一个类型值就当作已支持。其他媒介的接口约定见 [内容格式](media.md)。

## 3. 下载并运行 TXT 示例

[下载 NAS / WebDAV 专用示例包](omniread-webdav-kit.zip) · [查看书源 JSON 模板](nas-webdav/source.json)

包含适配器、书源 JSON、Docker 配置、凭据初始化工具和本机测试。它使用 Python 3 标准库；也可以在支持容器的 NAS 上运行。

准备一个小说目录，例如：

```text
Books/Novels/
├── 云间小记.txt
├── 远山与月.txt
└── 科幻/
    └── 星海来信.txt
```

在 NAS 上建立一个只读账号，只允许读取这个目录。解压下载包，在 `omniread-webdav-kit/nas-webdav` 目录运行：

```bash
export WEBDAV_URL='https://nas.example:5006/Books/Novels/'
export WEBDAV_USERNAME='reader'
export PUBLIC_BASE_URL='https://books.example'
python3 bridge.py
```

替换三个示例配置。程序依次询问 NAS 密码与**另行设置的书源访问密钥**，输入不回显；密钥至少 16 字节，之后在 APP 内输入相同值。不要把 NAS 管理员密码复用为书源密钥。

服务默认监听运行机器的 `127.0.0.1:8766`。使用 NAS 自带反向代理，将你自己的 `https://books.example` 转发到 `http://127.0.0.1:8766`。HTTPS 证书必须被手机信任，反向代理保留 `Authorization` 请求头及原始路径，不额外套一层网页登录或重定向。

`PUBLIC_BASE_URL` 只是告诉程序生成什么地址，**不会替你购买域名、配置 DNS 或申请证书**。该地址可以只在自己的局域网/VPN 可达，不要求将 NAS 或适配器公开给所有人。不要把外部路径前缀放入此项；示例使用专用 HTTPS 根地址。

如果你的 WebDAV 只有 HTTP，并且确实位于可信私有网络，可以显式运行 `python3 bridge.py --allow-http-webdav`。默认不允许 HTTP NAS，也不跳过 HTTPS 证书校验。

## 4. NAS 容器部署

在示例包的 `nas-webdav` 目录执行：

```bash
cp .env.example .env
# 编辑 .env，填写三个实际配置项
python3 setup_secrets.py
docker compose up -d --build
```

先确保已安装 Docker Compose。`setup_secrets.py` 交互写入权限为 0600 的 `secrets/webdav_password` 和 `secrets/bridge_api_key`，Compose 将它们作为只读 secret 文件挂载。脚本拒绝覆盖已有凭据。

默认主机端口仍只绑定 `127.0.0.1:8766`，由 NAS 主机上的 HTTPS 反向代理访问。**如果反向代理本身也运行在容器里**，应共享 Docker 网络，上游使用服务名 `omniread-webdav:8766`，不能把代理容器内的 `127.0.0.1` 当作 NAS 主机。

本示例支持上游 WebDAV Basic 认证。只支持 Digest、SSO、网页登录或跳转式认证的服务，需要另行适配；不要关闭认证来迁就示例。自签证书应正确安装到运行环境信任库。

## 5. 在 APP 里导入与登录

1. 先在手机浏览器打开你自己的 `https://books.example/source.json`，确认能拿到一份书源 JSON。
2. 在云书阁的书源管理中通过 URL 导入这个地址。
3. 打开该源的设置，使用运行服务时设置的**书源访问密钥**登录；这里不是 NAS 用户名或密码。
4. 在该源搜索 TXT 文件名，或进入「NAS 小说」发现列表。
5. 打开书籍、目录和正文。中文章名按常见“第 X 章 / Chapter N”识别；长章节按每段最多 12000 字符拆分。

原生 API 密钥登录依赖支持 `omnireadLogin` 的 APP 构建，首次支持的发行版本尚未公布。旧版导入成功也不代表能登录，不能在公开 JSON 内加入固定 `Authorization` 来绕过版本限制。

一份 TXT 对应一本小说，书名取文件名（去掉扩展名）。示例不猜作者、封面或简介。无章标题的文本会按长度分段。支持 UTF-8、带 BOM 的 UTF-16 和 GB18030；其他编码先自行转为 UTF-8。

## 6. 给适配作者的接口说明

| 接口 | 是否登录 | 返回 |
| --- | --- | --- |
| `GET /source.json` | 否 | 可导入的单个书源对象，不包含 NAS 凭据和访问密钥 |
| `POST /nas/login` | 否 | 接收 `{"apiKey":"用户输入的密钥"}`，返回一小时有效的 Bearer 令牌 |
| `GET /nas/session` | 是 | 有效时 204；过期时 401 |
| `GET /nas/search?q=关键词&page=1` | 是 | `{"books":[...]}`，每页 50 本，末页后为空 |
| `GET /nas/explore?page=1` | 是 | 同搜索列表，可不指定关键词 |
| `GET /nas/books/{id}` | 是 | 书籍详情，含 `toc` 目录地址 |
| `GET /nas/books/{id}/chapters?page=1` | 是 | 每页 200 章，`next` 指向下一页或为空 |
| `GET /nas/books/{id}/chapter/{index}` | 是 | `{"text":"章节正文"}` |

书籍 ID 根据 WebDAV 文件 URL 稳定生成；改名、移动路径或更换 NAS 域名会改变 ID。编辑 TXT 内容可能改变分章位置，原阅读进度需要重新定位。

适配器启动时只扫描文件目录元数据，之后搜索使用内存索引，不在每次搜索时递归遍历 NAS。只有打开章节目录/正文时才下载该本 TXT。正文只缓存一本，五分钟过期；不会写入磁盘。添加、删除或移动文件后，重启服务重建索引。

NAS 端 401/403 被转换为桥接服务的 502 `webdav_auth_failed`，避免把 NAS 故障误当成 APP 登录令牌失效。网页上不会返回原始 NAS 响应、地址、密码或堆栈。

## 7. 范围、限制与排查

| 项目 | 本示例的处理 |
| --- | --- |
| 书库规模 | 最多 5000 本 TXT、1000 个目录、20 层、10000 个返回条目；超限启动失败 |
| 上游响应 | 单目录 XML 最多 4 MiB；单本 TXT 最多 16 MiB；每个网络请求超时 15 秒 |
| 正文 | 单章段落最多 12000 字符；最多 10000 个分段；长章会拆分，不提供 EPUB 解析 |
| NAS 权限 | 只调用 PROPFIND / GET；拒绝越界路径、跨域 href、HTTP 重定向和 XML DTD/ENTITY |
| 访问范围 | 一把桥接密钥可读该实例索引中的全部小说；没有逐用户/逐书权限 |
| 会话 | 最多 100 个会话；令牌一小时过期，无自动续签；重启会清除会话 |
| 退出 | APP 退出清除本地凭据；服务端令牌到期或重启才失效 |
| 更新 | 新增/删除文件需重启；不是增量数据库或万人公共书库服务 |
| 服务性能 | 串行 HTTP 示例；读取大文件时会等待，适合个人或少量家庭用户联调 |

- 搜不到书：先确认启动时索引数量、目录账号权限和 `.txt` 扩展名；搜索按文件名匹配，不检索正文。
- 获取配置正常但 APP 登录失败：检查 APP 支持版本、手机证书信任、反向代理路径和访问密钥。
- 502 `webdav_auth_failed`：检查服务端 NAS 凭据，不需要反复清除 APP 书源登录。
- 启动失败：检查 WebDAV 地址末尾目录、Basic 认证、证书、目录/响应上限及重定向；工具不会打印敏感配置。
- 内容乱码：将文件转成 UTF-8 后重新读取；不要依赖对所有历史编码的自动识别。

这里的 GitHub Pages 网站仅托管文档和代码下载，**不会连接或保存你的 NAS 藏书**。适配器由每位用户在自己的 NAS/电脑运行，公开分发模板时不要携带 `.env`、`secrets/` 或真实会话令牌。

## 8. 运行示例测试

在解压后的 `nas-webdav` 目录执行：

```bash
python3 -m unittest discover -s . -p 'test_*.py'
```

测试启动本机模拟 WebDAV，验证目录扫描、中文路径、UTF-8/GB18030、登录/过期、搜索、目录分页、正文分段、凭据作用域、越界地址与重定向拒绝。不访问真实 NAS。真实 NAS 的证书、反向代理和 APP 端完整阅读仍需由部署者联调验收。
