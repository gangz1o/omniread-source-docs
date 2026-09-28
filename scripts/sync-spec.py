"""Explicitly sync the public specification between this Site and an iOS checkout."""
import argparse
import shutil
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('direction', choices=['import', 'export', 'check'])
parser.add_argument('ios_repository', type=Path)
args = parser.parse_args()
site = Path(__file__).resolve().parent.parent / 'content'
app = args.ios_repository.resolve() / 'docs/book-source'
if not app.is_dir():
    parser.error('Expected an iOS checkout containing docs/book-source')
names = ['README.md', 'rules.md', 'authentication.md', 'media.md', 'server.md', 'validation.md', 'source.schema.json']
names += [str(p.relative_to(site)) for folder in ['examples','demo'] for p in (site/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.name.startswith('.')]
different = []
for name in names:
    local, remote = site/name, app/name
    if args.direction == 'check':
        if not remote.exists() or local.read_bytes() != remote.read_bytes(): different.append(name)
    else:
        source, target = (remote,local) if args.direction == 'import' else (local,remote)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source,target)
if different:
    raise SystemExit('Specification drift:\n'+'\n'.join(different))
print(f'{args.direction}: {len(names)} public specification files')
