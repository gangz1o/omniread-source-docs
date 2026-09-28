"""Package only reviewed public fixtures; never walk user configuration directories."""
from pathlib import Path
import re
import zipfile

ROOT = Path('content')
NAS_FILES = ['.env.example', '.gitignore', 'Dockerfile', 'compose.yaml', 'README.md', 'bridge.py', 'webdav_client.py', 'test_bridge.py', 'source.json', 'setup_secrets.py']
COMMON = ['README.md', 'rules.md', 'authentication.md', 'media.md', 'server.md', 'validation.md', 'source.schema.json']
COMMON += [f'examples/{name}.json' for name in ['novel', 'comic', 'audio', 'video', 'account', 'key']]
COMMON += ['demo/server.py', 'demo/responses.json', 'demo/test_server.py', 'demo/assets/README.md', 'demo/assets/demo.mp4']
NAS = ['nas.md'] + ['nas-webdav/' + name for name in NAS_FILES]


def add(archive, path, data):
    info = zipfile.ZipInfo(path, (2026, 9, 28, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


for output, prefix, names in [('omniread-source-kit.zip', 'omniread-source-kit', COMMON + NAS), ('omniread-webdav-kit.zip', 'omniread-webdav-kit', NAS)]:
    with zipfile.ZipFile('dist/' + output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            data = (ROOT / name).read_bytes()
            if name == 'README.md':
                data = re.sub(r'^8\. \[维护说明\].*\n', '', data.decode(), flags=re.M).encode()
            add(archive, prefix + '/' + name, data)
        if output == 'omniread-source-kit.zip':
            add(archive, prefix + '/START_HERE.md', '# 独立资料包\n\n普通演示：python3 demo/server.py。NAS 示例：先阅读 nas.md。\n\n规范文档中的 docs/book-source/ 指 APP 仓库路径；独立资料包中去掉此前缀即可。Swift 命令需另行取得 APP 源码，本包不包含 Swift 校验器。\n')
print('Packaged public source and NAS kits from explicit file lists.')
