# 校验、验收与发布

返回 [规范入口](README.md)。校验分三层，不能相互替代。

## 1. 结构检查

将 [source.schema.json](source.schema.json) 配置为编辑器的本地 JSON Schema。它检查类型、必需字段、媒介值、规则字段拼写和认证声明形状。Schema 不能证明域名同源、脚本受支持、资源存在或访问授权成功。

仓库提供不联网、不执行书源脚本的静态工具：

```bash
swift run --package-path MetadataScraper booksource-check path/to/source.json
```

此工具需要可构建 MetadataScraper 的 macOS/Swift 开发环境。第一次构建可能拉取项目已有 SwiftSoup 依赖，但工具检查书源时不连接其中的端点。

它使用 APP 相同的导入解析器，检查 v1 基本必需规则、源身份重复、类型、根地址、原生登录声明/同源约束、限流格式和已知不支持脚本特征。它不是完整 JSON Schema 执行器，也不宣称覆盖每种语法错误。

退出码：`0` 无错误（可能仍有提示）；`1` 输入/规范错误；`2` 命令用法错误。输出使用源序号，不打印原始脚本、凭据或服务响应。

## 2. 固定响应回归

```bash
swift test --package-path MetadataScraper --filter BookSourceSpecificationExamplesTests
swift test --package-path MetadataScraper --filter BookSourceNativeLoginTests
python3 -m unittest discover -s docs/book-source/demo -p 'test_*.py'
```

示例测试直接读取本目录 JSON 和 `demo/responses.json`，通过真实规则引擎完成搜索、发现、详情、目录和四类章节解析。不会访问占位域名。登录测试使用受控响应验证令牌交换、保存、作用域、失效与竞态，不将测试密码发送到外部服务器。

## 3. 作者交付验收

| 分类 | 必测项 |
| --- | --- |
| 导入 | 单文件/URL；中文名称；无效 JSON；重复导入保留身份与启用状态 |
| 搜索 | 中文、空结果、多页、末页为空、字段缺失 |
| 详情 | 书名作者、简介、封面、目录入口；缺封面仍可读 |
| 目录 | 首章末章、正序、多页、不重复、不漏章；不能把下一章当正文下一页 |
| 小说 | 段落、特殊字符、正文分页、净化无误删 |
| 漫画 | 页数顺序、首尾页、大图、放大、横竖阅读、失效图片 |
| 有声书 | 播放、暂停、定位、切章、后台播放、资源过期 |
| 短剧 | 首末集、切集、定位、横竖屏、MP4/HLS、链接失效、观看进度恢复 |
| 原生登录 | 正确/错误凭据、取消、连点、退出、重启恢复、过期、401、403、断网重试 |
| 认证边界 | 换域名/端口/规则后重新登录；跨源不共享；导出不包含会话令牌 |
| 网页登录 | 用户能从打开的站点首页进入登录，Cookie 同步和失效可恢复 |
| 发布 | 写明作者版本、测过的 APP 构建、服务域名、媒介、认证方式和已知限制 |

静态检查不能验收真实服务器、证书、CDN、播放器格式或网络稳定性。作者应在实际 iPhone 上跑完受影响项目后再分发。

## 4. 常见问题

| 现象 | 排查顺序 |
| --- | --- |
| 能导入但没有结果 | 检查 searchUrl 返回体；bookList 是否选到列表；name/bookUrl 是否相对每个书籍节点求值 |
| header 不生效 | 顶层必须是 JSON 字符串；资源 headers 仅有白名单；后续页面 URL 不通用支持请求选项 |
| 详情正常但无目录 | 检查 tocUrl；ruleBookInfo.init 是否改变根；chapterList/name/url 是否匹配 |
| 漫画/音频内容为空 | bookSourceType / omnireadMediaType 是否正确；JSONPath 是否选中了对象而非字符串；改用 JSON.stringify 序列化资源对象 |
| 章节内容混入下一章 | nextContentUrl 误指向下一章，应删除并由目录控制 |
| 登录字段没有出现 | 旧 loginUi 不通用；确认 omnireadLogin 拼写、版本及 APP 是否包含本次实现 |
| 登录请求失败 | HTTPS 证书、同源端口、无重定向、POST JSON、HTTP 200 响应字段与字节上限 |
| 登录后媒体 401 | 媒体不附加原生令牌；服务器应返回独立可访问资源/签名 URL |
| 升级书源后要求重登 | 影响执行的字段指纹改变，是预期凭据隔离行为 |
| 开启网页登录却无法用 token | Cookie 和原生 Bearer 是两种不同模式，选择一种 |
| 无“不兼容”警告却仍失败 | 特征扫描只捕获部分未支持方法，不能证明脚本可执行或站点在线 |

## 5. 发布包建议

- `source.json`：通过检查的正式配置，替换所有占位地址。
- `README.md`：作者、服务说明、内容范围、导入方式、登录方式、APP 支持版本。
- `CHANGELOG.md`：版本、日期、变更、是否需重登/重新导入。
- 自有或脱敏 fixtures 与回归步骤，不附实际用户凭据、私有正文或个人 Cookie。

普通更新通过原 URL 提供最新 JSON，让用户重新导入。v1 没有通用自动更新周期、更新签名或最小 APP 版本执行器，不能仅增加一个字段便宣称这些能力已启用。
