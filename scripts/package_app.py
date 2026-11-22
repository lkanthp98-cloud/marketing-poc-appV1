"""Package source, compiled UI, local sample data and verification evidence for Databricks Apps."""
import hashlib
import json
import zipfile
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
EXCLUDED={'.venv','node_modules','__pycache__','.git','playwright-report','test-results'}


def main():
    files=sorted(p for p in APP.rglob('*') if p.is_file() and not (set(p.relative_to(APP).parts)&EXCLUDED)
        and p.name!='PACKAGE_MANIFEST.json' and p.suffix not in {'.pyc','.zip','.log'})
    manifest={p.relative_to(APP).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    path=APP/'PACKAGE_MANIFEST.json'
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    output=APP.parent/'marketing-analytics-databricks.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as archive:
        for p in files+[path]:archive.write(p,p.relative_to(APP).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert all(hashlib.sha256(archive.read(name)).hexdigest()==digest for name,digest in manifest.items())
        assert 'app.yaml' in archive.namelist() and 'data/workspace_contract.json' in archive.namelist()
        assert all(not (set(Path(name).parts)&EXCLUDED) for name in archive.namelist())
    print(f'Verified package: {output} ({len(files)+1} files, {output.stat().st_size:,} bytes)')


if __name__=='__main__':main()
