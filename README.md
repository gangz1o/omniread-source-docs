# 云书阁开发者文档网站

独立维护的静态文档项目。构建仅依赖本目录，不读取 iOS 项目、不编译 APP、不连接示例域名。`content/` 保存 Markdown 规范、Schema、六份书源和演示程序；`assets/` 保存网站样式及复制交互；`dist/` 是生成的完整部署产物。

## 本地维护

需要 Node.js（支持 ES modules）、npm 和 Python 3。`marked` 是唯一构建依赖，用于标准 Markdown/GFM 表格解析；没有浏览器运行时依赖。

```bash
npm ci
# 修改 content/*.md、content/examples/*.json 或 assets/*
npm run build
npm run check
npm run dev
```

打开 http://127.0.0.1:4317 ，修改后重新构建并刷新浏览器。全部页面也能部署到普通静态主机，入口为 `dist/index.html`；站内链接采用相对路径。

## 规范与 APP 保持一致

网站有自己的内容快照，可以移到独立仓库继续维护。接口协议改动必须同时修改 APP 实现/测试；发布网站本身不会让已发布的 APP 获得新能力。

```bash
# 从网站导出规范到指定 APP 仓库（只覆盖公开规范文件）
python3 scripts/sync-spec.py export /absolute/path/to/OmniRead
# APP 中修改规范后，可反向同步
python3 scripts/sync-spec.py import /absolute/path/to/OmniRead
# CI 或发版前检查两边有无差异
python3 scripts/sync-spec.py check /absolute/path/to/OmniRead
```

同步不包含内部 `implementation.md`、UI 变更单、构建日志、用户凭据或 APP 源码。同步方向必须显式选择；应先审查双方未提交改动，不要双向自动覆盖。

新增页面须更新 `scripts/build.mjs` 的页面导航。规范文档中的 `.md` 链接自动转换为网站路由；网页端演示命令适配下载包目录。书源示例与 Schema 按原始字节复制，资料包打包允许列表中的公开内容。资料包不包含 Swift 校验器；Swift 命令需要 APP 源码和 macOS/Swift 环境。

## 公网部署与更新

使用 GitHub Pages 的免费公开仓库托管；不需要购买服务器或域名。

- 文档网站：https://gangz1o.github.io/omniread-source-docs/
- 独立源码：https://github.com/gangz1o/omniread-source-docs
- 发布分支：`codex/docs-site`
- 自动发布配置：`.github/workflows/pages.yml`

修改 `content/` 或 `assets/` 后，运行 `npm run build` 和 `npm run check`，提交并推送到发布分支。GitHub Actions 会重新构建、检查链接、测试演示服务，并把 `dist/` 发布到 Pages。也可在仓库 Actions 页面手动运行 Deploy documentation。以 Actions 部署成功及公网访问结果为准。

生成目录 `dist/` 不提交。原 Sites 的本地站点记录留在忽略的 `.openai/` 中，GitHub Pages 不读取它，也不会上传它。此独立仓库只包含公开文档及网站源码，不包含 iOS APP 源码或内部验收记录。
