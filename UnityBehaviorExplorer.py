from flask import Flask
import glob
import os
import json
from collections import namedtuple
import collections
import re
from functools import lru_cache
import textwrap

try:
    from tqdm import tqdm
except ImportError:
    print("tqdm not installed, using dumb iterator")

    def tqdm(iterable, *args):
        yield from iterable

FileID = namedtuple("FileID", ["fileName", "pathId"])

def safe(x):
    return x.replace('#', '$')


file_paths = sorted(glob.glob("*/MonoBehaviour/*"))

referencesFrom = collections.defaultdict(list)
referencedBy = collections.defaultdict(list)
referencedAs = collections.defaultdict(lambda: collections.defaultdict(list))

def findRefs(x, name=None):
    if isinstance(x, dict):
        if 'm_FileName' in x:
            id_ = FileID(x['m_FileName'], str(x['m_PathID']))
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
        referencesFrom[source].append(target)
        referencedBy[target].append(source)
        referencedAs[target][source].append(refd_as)

@lru_cache(10000)
def getReferencesHtml(file_id):
    if file_id not in referencedBy:
        return '<p>No references to this file</p>'

    return "<p>Referenced by:</p>" + "\n".join(["<li>" + fileIdToLink(ref) + " as " + ", ".join(referencedAs[file_id][ref]) + "</il>" for ref in set(referencedBy[file_id])])

@lru_cache(10000)
def fileIdToName(ref):
    try:
        assert ref.fileName is not None
        target_glob = os.path.join(ref.fileName, "*", f"*#{ref.pathId}.*")
        targetNames = glob.glob(target_glob)

        assert len(targetNames) == 1
        targetName = targetNames[0].replace('\\', '/')
        return targetName
    except (AssertionError, IndexError):
        return f"Unknown! ({ref.fileName}/{ref.pathId})"

def fileIdToLink(ref):
    try:
        targetName = fileIdToName(ref)
        link = safe(f"/file/{targetName}")
        return f"<a href='{link}'>{targetName}</a>"
    except (AssertionError, IndexError):
        return f"<em>Unknown!</em> ({ref.fileName}/{ref.pathId})"


def graphFileRefs(root):

    def fikey(file_id):
        return f"{str(file_id.fileName)}.{file_id.pathId}".replace(' ', '_').replace(')', '').replace('(', '')  

    def _graphFileRefs(root, visited=[], by=True):
        if by:
            list_ = referencedBy
        else:
            list_ = referencesFrom

        for ref in list_[root]:
            for refd_as in referencedAs[root][ref] + referencedAs[ref][root]:
                key = (root, refd_as, ref)
                if key in visited or len(visited) > 60:
                    continue

                visited.append(key)

                to_str = f"{fikey(ref)}[{fileIdToName(ref).replace(' ','_').replace(')', '').replace('(', '').replace('MonoBehaviour/', '') }]"
                from_str = f"{fikey(root)}[{fileIdToName(root).replace(' ','_').replace(')', '').replace('(', '').replace('MonoBehaviour/', '') }]"
                if by:
                    yield f"  {to_str}-->|{refd_as}| {from_str}"
                else:
                    yield f"  {from_str}-->|{refd_as}| {to_str}"

                yield f"  click {fikey(ref)} \"{safe(f'/file/{fileIdToName(ref)}')}\""
                yield f"  click {fikey(root)} \"{safe(f'/file/{fileIdToName(root)}')}\""

                yield from _graphFileRefs(ref, visited, by)

    ret = "graph TD\n" + "\n".join(list(_graphFileRefs(root, by=True))) + "\n" + "\n".join(list(_graphFileRefs(root, by=False)))
    return ret


# graphFileRefs("sharedassets25.assets", "1607")

if __name__ == "__main__":
    app = Flask(__name__)

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
        (path_id,) = re.match(r".*\#(\d+)\.json", filename).groups()
        with open(os.path.join(archive, 'MonoBehaviour', filename)) as f:
            parsed = json.load(f)

        fileId = FileID(archive, path_id)
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
        ret = '<script>mermaid.initialize({startOnLoad:true});</script>' + f'''<h1>{fileIdToLink(fileId)}</h1>
        {references}
        <pre>{json.dumps(parsed, indent=4, sort_keys=False)}</pre>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <div class='mermaid'>{graphFileRefs(fileId)}</div>'''
        return f'<html><head></head><body>{ret}</body></html>'


    app.run()
