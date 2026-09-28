"""Create initial Docker secret files without shell history or echoed input."""
import getpass
import os
from pathlib import Path

if __name__ == '__main__':
    root = Path(__file__).resolve().parent / 'secrets'
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    files = [root / 'webdav_password', root / 'bridge_api_key']
    if any(path.exists() for path in files):
        raise SystemExit('凭据文件已存在；为避免覆盖，本工具只用于首次配置。')
    password = getpass.getpass('输入 NAS 只读账号密码（不回显）：')
    key = getpass.getpass('设置书源访问密钥（至少 16 字节，不回显；稍后在 APP 输入相同值）：')
    if not password or not 16 <= len(key.encode()) <= 4096 or key != key.strip():
        raise SystemExit('密码不能为空，密钥须为 16–4096 字节且首尾不能有空白。未写入文件。')
    for path, value in zip(files, [password, key]):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(value)
    print('凭据已写入本地受限权限文件；不要上传 secrets/ 或分发这两个文件。')
