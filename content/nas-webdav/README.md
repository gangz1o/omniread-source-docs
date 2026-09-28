# WebDAV → 云书阁 TXT 书源

这是部署在你自己 NAS / 电脑上的只读适配示例，Python 3 标准库即可运行。完整指南见资料包外层的 `nas.md`，在线版：https://gangz1o.github.io/omniread-source-docs/nas.html 。

## Python 启动

```sh
export WEBDAV_URL='https://nas.example:5006/Books/Novels/'
export WEBDAV_USERNAME='reader'
export PUBLIC_BASE_URL='https://books.example'
python3 bridge.py
```

将示例地址替换为自己的地址。启动会以不回显方式询问 NAS 密码和另设的书源密钥，随后扫描目录。服务默认监听本机 8766；由你自己的 HTTPS 反向代理转发到 `http://127.0.0.1:8766`。APP 需要信任 HTTPS 证书，不能把 `PUBLIC_BASE_URL` 当成自动申请域名或证书的功能。

访问 `https://books.example/source.json` 获取实际配置，APP 导入后在书源设置中以刚才设置的密钥登录（不是 NAS 密码）。本示例依赖支持 `omnireadLogin` 的 APP 构建。

## 容器启动（需要已安装 Docker Compose）

```sh
cp .env.example .env
# 编辑 .env：填入实际 WebDAV 地址、只读用户名、桥接 HTTPS 地址
python3 setup_secrets.py
docker compose up -d --build
```

默认端口只发布在 NAS 主机的 127.0.0.1，由主机反向代理连接。若反向代理也在容器中，应把两者放进同一 Docker 网络，并将上游指向 `omniread-webdav:8766`。容器内的 127.0.0.1 不是 NAS 主机。服务自己不终止 TLS。

`secrets/` 的两个文件权限为 0600，仅供 Compose 的只读 secret 挂载；生产部署可用 NAS 自带 secret 管理设施。不要上传它们、`.env` 或填写过真实凭据的配置。

## 行为和边界

- 仅调用 NAS 的 PROPFIND / GET，只索引指定目录内的 TXT。
- 搜索使用启动时的内存索引；添加/删除/移动小说后重启服务重新扫描。
- 单本 TXT 上限 16 MiB；按常见章名和 12000 字符长度拆分，UTF-8 / BOM UTF-16 / GB18030。
- 仅一份正文缓存，5 分钟过期；不会写入磁盘。更改原文件可能使章节序号发生变化。
- API 密钥是独立的书源访问密钥，可访问该实例整个索引。不是多用户权限服务。
- 令牌 1 小时过期，不自动刷新；APP 退出仅清本地会话。重启服务清除所有令牌。
- HTTPS NAS 默认严格验证证书；可信内网 HTTP 必须显式传 `--allow-http-webdav`，不会关闭 HTTPS 证书校验。
- NAS 必须支持 Basic 认证、Depth: 1 的 UTF-8 DAV:multistatus 及 collection 属性。重定向、跨域 href、越界路径、DTD/ENTITY 被拒绝。
- 目录上限：1000 个目录、20 层、10000 个返回条目、5000 本 TXT；超限启动失败，不返回残缺书库。
- 适用于个人小规模联调。串行 HTTP 服务，不提供高并发、账户注册、在线修改 NAS、增量数据库或自动重建索引。

## 本地测试

```sh
python3 -m unittest discover -s . -p 'test_*.py'
```

测试自行启动本机 WebDAV fixture，不连接你的 NAS，也不会读取部署凭据。
