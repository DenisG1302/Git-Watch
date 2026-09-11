#!/usr/bin/env python3
"""Create a consistent private backup while the service is running."""
import os
from pathlib import Path
import sys
import time
import tarfile
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from gitwatch.store import Store

project=Path(__file__).resolve().parent.parent
data=Path(os.getenv('GITWATCH_DATA',str(project/'data')))
output=project/'backups'
output.mkdir(exist_ok=True,mode=0o700)
archive=output/('gitwatch-'+time.strftime('%Y%m%d-%H%M%S')+'.tar.gz')
with tempfile.TemporaryDirectory() as temp:
    snapshot=Path(temp)/'gitwatch.sqlite3'
    Store(data).backup(snapshot)
    with tarfile.open(archive,'w:gz') as tar:
        os.chmod(archive,0o600)
        tar.add(snapshot,arcname='data/gitwatch.sqlite3')
        for item in data.iterdir():
            if item.is_file() and not item.name.startswith('gitwatch.sqlite3'):
                tar.add(item,arcname='data/'+item.name)
print(archive)
