from flask import Flask
import glob
import os
import json
from collections import namedtuple
import collections
import re
from functools import lru_cache

try:
    raise ImportError
    from tqdm import tqdm
except ImportError:
    print("tqdm not installed, using dumb iterator")

    def tqdm(iterable, *args):
        yield from iterable

FileID = namedtuple("FileID", ["fileName", "pathId"])

def safe(x):
    return x.replace('#', '$')


file_paths = sorted(glob.glob("*/MonoBehaviour/*"))

referencesTo = {}
referencedBy = collections.defaultdict(list)
referencedAs = collections.defaultdict(lambda: collections.defaultdict(list))

def findRefs(x, name=None):
    if isinstance(x, dict):
        if 'm_FileName' in x:
            id_ = FileID(x['m_FileName'], x['m_PathID'])
            yield (id_, name)
        for k, v in x.items():
            yield from findRefs(v, name=k)
    elif isinstance(x, list):
        for v in x:
            yield from findRefs(v, name=name)

print("Building references...")
for path in tqdm(file_paths):
    (folder_name, path_id) = re.match(r"(.*?)\/.*\#(\d+)\.json", path.replace("\\", "/")).groups()
    source = FileID(folder_name, path_id)
    with open(os.path.join(path), 'r', encoding="utf-8") as fp:
        parsed = json.load(fp)

    # todo make this faster
    for target, refd_as in findRefs(parsed):
        referencedBy[target].append(source)
        referencedAs[target][source].append(refd_as)

@lru_cache(10000)
def getReferencesHtml(file_id):
    if file_id not in referencedBy:
        return '<p>No references to this file</p>'

    print(file_id)
    for ref in referencedBy[file_id]:
        print(ref, referencedAs[file_id][ref])
    return "<p>Referenced by:</p>" + "\n".join(["<li>" + fileIdToLink(ref) + " as " + ", ".join(referencedAs[file_id][ref]) + "</il>" for ref in set(referencedBy[file_id])])

@lru_cache(10000)
def fileIdToLink(ref):
    try:
        assert ref.fileName is not None
        target_glob = os.path.join(ref.fileName, "*", f"*#{ref.pathId}.*")
        targetNames = glob.glob(target_glob)

        assert len(targetNames) == 1
        targetName = targetNames[0].replace('\\', '/')
        link = safe(f"/file/{targetName}")
        return f"<a href='{link}'>{targetName}</a>"
    except (AssertionError, IndexError):
        return f"<em>Unknown!</em> ({ref.fileName}/{ref.pathId})"


app = Flask(__name__)
print("Started", app)

@app.route('/')
def index():
    ret = '\n'.join(
        '<p><a href={}>{}</a></p>'.format('"file/' + safe(f) + '"', f)
        for f in file_paths
    )
    return f'<html><head></head><body>{ret}</body></html>', 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/file/<archive>/MonoBehaviour/<filename>')
def show(archive, filename):
    filename = filename.replace('$', '#')
    print(filename)
    (path_id,) = re.match(r".*\#(\d+)\.json", filename).groups()
    with open(os.path.join(archive, 'MonoBehaviour', filename)) as f:
        parsed = json.load(f)

    fileId = FileID(archive, int(path_id))
    references = getReferencesHtml(fileId)

    def traverse(x):
        if isinstance(x, dict):
            if 'm_FileName' in x:
                filename = x['m_FileName']
                path_id = x['m_PathID']
                targetId = FileID(filename, path_id)
                try:
                    x["ref"] = fileIdToLink(targetId)
                except:
                    print("Failed ref", targetId)
            for k, v in x.items():
                traverse(v)
        elif isinstance(x, list):
            for v in x:
                traverse(v)

    traverse(parsed)
    ret = f'<h1>{fileIdToLink(fileId)}</h1>{references}<pre>{json.dumps(parsed, indent=4, sort_keys=False)}</pre>'
    return f'<html><head></head><body>{ret}</body></html>'

app.run()
