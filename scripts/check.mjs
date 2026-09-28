import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const root=resolve('dist');
const pages=readdirSync(root).filter(name=>name.endsWith('.html'));
let links=0;
for(const page of pages){
  const html=readFileSync(`${root}/${page}`,'utf8');
  assert(html.includes('lang="zh-CN"'), `${page}: missing document language`);
  assert(!/implementation\.md|\/Users\/|\.xcresult/.test(html), `${page}: internal maintenance data`);
  for(const match of html.matchAll(/(?:href|src)="([^"]+)"/g)){
    const href=match[1];
    if(/^(https?:|data:|mailto:)/.test(href)) continue;
    const [file,fragment]=href.split('#');
    const target=resolve(root,file?.replace(/^\//,'') || page);
    assert(target.startsWith(root+'/'), `outside output: ${href}`);
    assert(existsSync(target), `${page}: broken link ${href}`);
    if(fragment) assert(readFileSync(target,'utf8').includes(`id="${decodeURIComponent(fragment)}"`), `${page}: missing anchor ${href}`);
    links++;
  }
}
for(const file of readdirSync(`${root}/examples`)) JSON.parse(readFileSync(`${root}/examples/${file}`,'utf8'));
JSON.parse(readFileSync(`${root}/source.schema.json`,'utf8'));
JSON.parse(readFileSync(`${root}/nas-webdav/source.json`,'utf8'));
console.log(`Checked ${pages.length} pages, ${links} local links/anchors, six base examples, NAS source and schema.`);
