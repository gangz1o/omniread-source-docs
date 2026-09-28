import { readFileSync, writeFileSync, mkdirSync, cpSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { marked } from 'marked';

const pages = [
  ['index', 'README', '快速上手', '从一份 JSON 开始接入云书阁。'],
  ['rules', 'rules', '请求与规则', '把你的内容接口映射到搜索、目录与章节。'],
  ['media', 'media', '内容格式', '小说、漫画、有声书与短剧的资源约定。'],
  ['authentication', 'authentication', '登录接入', '账号密码、API 密钥与网页登录。'],
  ['server', 'server', '自建服务与联调', '运行示例服务，验证完整阅读流程。'],
  ['validation', 'validation', '校验与发布', '从结构检查到真实设备验收。'],
  ['downloads', null, '示例与下载', '完整书源、JSON Schema 和本地演示服务。'],
];
const exampleNames = {novel:'小说', comic:'漫画', audio:'有声书', video:'短剧', account:'账号密码登录', key:'API 密钥登录'};
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const slug = text => text.toLowerCase().replace(/<[^>]*>/g,'').replace(/[^\p{L}\p{N}\s-]/gu,'').trim().replace(/\s+/g,'-');
mkdirSync('dist', {recursive:true});
cpSync('assets', 'dist/assets', {recursive:true});
cpSync('content/examples', 'dist/examples', {recursive:true});
cpSync('content/source.schema.json', 'dist/source.schema.json');
// Reproducible archive; only the explicitly public author resources are included.
execFileSync('python3', ['-c', `from pathlib import Path
import zipfile, re
root=Path('content')
with zipfile.ZipFile('dist/omniread-source-kit.zip','w',zipfile.ZIP_DEFLATED) as z:
 for path in sorted(root.rglob('*')):
  if path.is_file() and '__pycache__' not in path.parts and not path.name.startswith('.'):
   info=zipfile.ZipInfo('omniread-source-kit/'+str(path.relative_to(root)),(2026,9,28,0,0,0))
   info.compress_type=zipfile.ZIP_DEFLATED
   data=path.read_bytes()
   if path.name=='README.md' and path.parent==root:
    data=re.sub(r'^8\\. \\[维护说明\\].*\\n','',data.decode(),flags=re.M).encode()
   z.writestr(info,data)
 info=zipfile.ZipInfo('omniread-source-kit/START_HERE.md',(2026,9,28,0,0,0))
 z.writestr(info,'# 独立资料包\\n\\n在本目录运行 python3 demo/server.py，访问 http://127.0.0.1:8765/sources.json。运行回归：python3 -m unittest discover -s demo。\\n\\n规范文档中的 docs/book-source/ 指 APP 仓库路径；独立资料包中去掉此前缀即可。Swift 命令需要另行取得 APP 源码，本包不包含 Swift 校验器。登录联调需要设备信任的 HTTPS，详见 server.md。\\n')
`]);
const favicon = encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#192632"/><path d="M7 8h6l3 2 3-2h6v16h-6l-3 2-3-2H7z" fill="none" stroke="#e5bc72" stroke-width="2"/><path d="M16 10v16" stroke="#e5bc72" stroke-width="2"/></svg>');

for (let position=0; position<pages.length; position++) {
  const [route, file, title, description] = pages[position];
  let toc = [];
  const renderer = new marked.Renderer();
  const seen = new Map();
  renderer.heading = function({tokens, depth}) {
    const text = this.parser.parseInline(tokens);
    const base = slug(text);
    const count = seen.get(base) ?? 0; seen.set(base,count+1);
    const id = base+(count?`-${count}`:'');
    if(depth===2) toc.push([id,text.replace(/<[^>]*>/g,'')]);
    return `<h${depth} id="${id}">${text}<a class="anchor" href="#${id}" aria-label="链接到此节">#</a></h${depth}>`;
  };
  renderer.link = function({href,title,tokens}) {
    href = href.replace(/^README\.md/, 'index.html').replace(/^(rules|media|authentication|server|validation)\.md/, '$1.html');
    const download = /(?:\.json|\.zip)$/.test(href) ? ' download' : '';
    return `<a href="${escape(href)}"${download}${title?` title="${escape(title)}"`:''}>${this.parser.parseInline(tokens)}</a>`;
  };
  let body;
  if(file) {
    let md=readFileSync(`content/${file}.md`,'utf8');
    md=md.replace(/^# .+\n/, '').replace(/^返回 \[规范入口\]\(README.md\)。/m,'');
    md=md.replace(/^8\. \[维护说明\].*\n/m,'');
    md=md.replace('以本目录示例和回归测试为验收基线。','以配套示例和回归测试为验收基线。');
    if(route==='index') md=md.replace('状态：仓库实现与开发者联调规范。日期：2026-09-28。','');
    // Site instructions work with the downloadable kit independently of the iOS repository.
    if(route==='server') md=md.replace('仓库根目录执行：','下载 [开发者资料包](omniread-source-kit.zip)，解压后在 `omniread-source-kit` 目录执行：').replaceAll('docs/book-source/demo/','demo/');
    if(route==='validation') md=md.replace('仓库提供不联网、不执行书源脚本的静态工具：','APP 源码仓库提供不联网、不执行书源脚本的静态工具。以下 Swift 命令在 APP 仓库根目录执行，需要取得源码；资料包不包含 Swift 工具或预编译二进制：');
    if(route==='index') md=md.replace('```bash\nswift run', '以下命令在 APP 源码仓库根目录执行；仅使用资料包时，先参考「校验与发布」的 Schema 检查。\n\n```bash\nswift run');
    body=marked.parse(md,{renderer,gfm:true});
  } else {
    body=`<p>选择与你的内容和认证方式匹配的示例，替换占位域名后再导入 APP。所有文件均为可编辑的原始配置。</p>
    <div class="example-grid">${Object.entries(exampleNames).map(([key,label],i)=>`<a class="example" href="examples/${key}.json" download><span class="example-number">0${i+1}</span><strong>${label}</strong><code>${key}.json</code><span class="download-label">下载 JSON ↓</span></a>`).join('')}</div>
    <h2 id="schema">JSON Schema</h2><p>用于编辑器中的字段、类型和必填项检查。它不能替代真实接口和设备联调。</p><p><a class="button" href="source.schema.json" download>下载 source.schema.json ↓</a></p>
    <h2 id="kit">完整开发者资料包</h2><p>包含六份书源、六篇 Markdown 文档、Schema、Python 演示服务、固定响应和自制测试视频。仅依赖 Python 3 标准库即可运行演示服务。</p><p><a class="button" href="omniread-source-kit.zip" download>下载资料包 ZIP ↓</a></p>
    <pre><code>cd omniread-source-kit\npython3 demo/server.py</code></pre><p>启动后访问 <code>http://127.0.0.1:8765/sources.json</code>。原生登录需要设备信任的 HTTPS；具体步骤见<a href="server.html">自建服务与联调</a>。</p>
    <div class="note">示例中的 <code>demo.omniread.invalid</code> 是占位地址，没有在线演示服务。资料包不包含 APP 源码或 Swift 校验器。</div>`;
    toc=[['schema','JSON Schema'],['kit','完整开发者资料包']];
  }
  body=body.replace(/<table>/g,'<div class="table-scroll" tabindex="0" role="region" aria-label="字段参考表，可横向滚动"><table>').replace(/<\/table>/g,'</table></div>');
  const nav=pages.map(([path,,label],i)=>`<a href="${path}.html" ${path===route?'aria-current="page"':''}><span class="nav-number">0${i+1}</span>${label}</a>`).join('');
  const previous=pages[position-1], next=pages[position+1];
  writeFileSync(`dist/${route}.html`, `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark"><title>${title} · 云书阁开发文档</title><meta name="description" content="${description}"><link rel="icon" type="image/svg+xml" href="data:image/svg+xml,${favicon}"><link rel="stylesheet" href="assets/site.css"><script src="assets/site.js" defer></script></head>
<body><a class="skip" href="#main">跳到正文</a><header class="topbar"><a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">云</span><strong>云书阁</strong><span class="brand-divider"></span><span class="brand-caption">开发文档</span></a><div class="header-actions"><span class="version">规范 v1.0</span><button class="menu-toggle" aria-expanded="false" aria-controls="navigation">目录</button></div></header>
<div class="layout"><aside class="sidebar" id="navigation"><div class="nav-label">书源接入指南</div><nav aria-label="文档导航">${nav}</nav><div class="sidebar-note"><strong>先让一个源跑起来</strong><p>准备响应 → 写规则 → 导入联调 → 发布 JSON</p><a href="downloads.html">获取示例文件 ↗</a></div><div class="sidebar-meta">v1 开发者联调规范<br>更新于 2026 年 9 月 28 日</div></aside>
<main id="main" tabindex="-1"><div class="breadcrumb">书源开发 / ${title}</div><div class="page-heading"><p class="eyebrow">OMNIREAD DEVELOPERS</p><h1>${title}</h1><p class="description">${description}</p></div><div class="release-note"><span class="release-tag">版本说明</span><span>原生登录与显式短剧类型需新版 APP 支持，首次支持的发行版本尚未公布。</span></div><article>${body}</article><nav class="page-nav" aria-label="相邻文档">${previous?`<a href="${previous[0]}.html"><small>上一页</small>← ${previous[2]}</a>`:'<span></span>'}${next?`<a class="next" href="${next[0]}.html"><small>下一页</small>${next[2]} →</a>`:'<span></span>'}</nav><footer>云书阁 · 书源开发规范 v1.0 <span>面向书源作者与自建服务维护者</span></footer></main>
<aside class="toc" aria-label="本页目录"><div class="nav-label">本页内容</div>${toc.map(([id,label])=>`<a href="#${id}">${escape(label)}</a>`).join('')}</aside></div><span id="copy-status" class="sr-only" role="status" aria-live="polite"></span></body></html>`);
}
writeFileSync('dist/404.html', '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>页面未找到 · 云书阁</title><link rel="stylesheet" href="https://gangz1o.github.io/omniread-source-docs/assets/site.css"><main><h1>页面未找到</h1><p>文档地址可能已变更。</p><a href="https://gangz1o.github.io/omniread-source-docs/">返回开发文档</a></main></html>');
console.log(`Generated ${pages.length} documentation pages, six examples, schema and developer kit.`);
