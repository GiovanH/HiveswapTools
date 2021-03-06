from flask import Flask
import glob
import os
import json
from collections import namedtuple
import collections
import re
from functools import lru_cache
import textwrap
import logging
import pickle
import base64
import itertools

try:
    from tqdm import tqdm
except ImportError:
    print("tqdm not installed, using dumb iterator")

    def tqdm(iterable, *args):
        yield from iterable

FileID = namedtuple("FileID", ["fileName", "pathId"])

def safe(x):
    return x.replace('#', '$')


game_root = "."

file_paths = sorted(glob.glob(game_root + "/*/MonoBehaviour/*"))

def findRefs(x, name=""):
    if isinstance(x, dict):
        if 'm_FileName' in x:
            id_ = FileID(x['m_FileName'], str(x['m_PathID']))
            yield (id_, name)
        for k, v in x.items():
            yield from findRefs(v, name=name + "." + k)
    elif isinstance(x, list):
        for v in x:
            yield from findRefs(v, name=name)

def ddictlist():
    # module level function, picklable
    return collections.defaultdict(list)


referencesFrom = collections.defaultdict(list)
referencedBy = collections.defaultdict(list)
referencedAs = collections.defaultdict(ddictlist)

reference_cache_filepath = "refs.pickle"
try:
    with open(reference_cache_filepath, "rb") as fp:
        (referencesFrom, referencedBy, referencedAs) = pickle.load(fp)
    print("Loaded cached references")
except (FileNotFoundError, EOFError):
    print("Building references...")
    for path in tqdm(file_paths):
        (folder_name, path_id) = re.match(r"(.*?)\/.*\#(\d+)\.json", path.replace("\\", "/")).groups()
        source = FileID(folder_name, path_id)
        with open(os.path.join(path), 'r', encoding="utf-8") as fp:
            parsed = json.load(fp)

        # todo make this faster
        for target, refd_as in findRefs(parsed):
            if target.fileName is not None:
                referencesFrom[source].append(target)
                referencedBy[target].append(source)
                referencedAs[target][source].append(refd_as)

    with open(reference_cache_filepath, "wb") as fp:
        tup = (referencesFrom, referencedBy, referencedAs,)
        pickle.dump(tup, fp)

def getReferencesHtml(file_id):
    if file_id not in referencedBy:
        return '<p>No references to this file</p>'

    return "<p>Referenced by:</p><ul>" + "\n".join(["<li>" + fileIdToLink(ref) + " as " + ", ".join(referencedAs[file_id][ref]) + "</li>" for ref in set(referencedBy[file_id])]) + "</ul>"

@lru_cache(10000)
def fileIdToName(ref):
    try:
        assert ref.fileName is not None
        if ref.fileName == ".":
            # TEMPORARY HACK
            archive = "*"
        else:
            archive = ref.fileName
        target_glob = os.path.join(archive, "*", f"*#{ref.pathId}.*")
        targetNames = glob.glob(target_glob)

        assert len(targetNames) == 1
        targetName = targetNames[0].replace('\\', '/')
        return targetName
    except (AssertionError, IndexError):
        logging.warning(ref)
        logging.warning(target_glob)
        logging.warning(targetNames)
        return f"Unknown! ({ref.fileName}/{ref.pathId})"

def fileIdToLink(ref):
    try:
        targetName = fileIdToName(ref)
        link = safe(f"/file/{targetName}")
        return f"<a href='{link}'>{targetName}</a>"
    except (AssertionError, IndexError):
        logging.warning(ref, exc_info=True)
        return f"<em>Unknown!</em> ({ref.fileName}/{ref.pathId})"


def graphFileRefs(root, max_dist=1):

    def fikey(file_id):
        return f"{str(file_id.fileName)}.{file_id.pathId}".replace(' ', '_').replace(')', '').replace('(', '')  

    def _graphFileRefs(root, visited=None, mermaid_defined=None, recursive=1):
        if visited is None:
            visited = list()
        if mermaid_defined is None:
            mermaid_defined = list()

        keys = []
        # print(root, recursive)

        if root.fileName is None:
            return

        for source in referencedBy[root]:
            for refd_as in referencedAs[root][source]:
                # Root is referenced by name refd_as by source
                key = (root, refd_as, source)
                keys.append(key)

        for target in referencesFrom[root]:
            for refd_as in referencedAs[target][root]:
                # Target is referenced by name refd_as by root
                key = (target, refd_as, root)
                keys.append(key)

        # print(keys)

        for key in keys:
            (target, refd_as, source) = key

            if key in visited:
                continue

            if refd_as in [".nodeKnobs"]:
                recursive += 1

            # print(key)

            visited.append(key)

            for node in [source, target]:
                key = fikey(node)
                if key not in mermaid_defined:
                    po, pc = ("[", "]")

                    # Mark root node w/ stadium
                    if len(visited) == 1 and node is root:
                        po, pc = ("([", "])")

                    yield f"  {key}{po}{fileIdToName(node).replace(' ','_').replace(')', '').replace('(', '').replace('MonoBehaviour/', '')}{pc}"
                    yield f"  click {key} \"{safe(f'/file/{fileIdToName(node)}')}\""

                    if not (recursive > 0):
                        yield f"  style {key} fill:#fff0"

                    mermaid_defined.append(key)

            to_str = f"{fikey(target)}"
            from_str = f"{fikey(source)}"
            yield f"  {from_str}-->|{refd_as}| {to_str}"

            if recursive > 0:
                yield from _graphFileRefs(source, visited, mermaid_defined, recursive=recursive-1)
                yield from _graphFileRefs(target, visited, mermaid_defined, recursive=recursive-1)

    ret = "graph LR\n" + "\n".join(list(_graphFileRefs(root)))
    return ret


# graphFileRefs("sharedassets25.assets", "1607")

b64 = None

if __name__ == "__main__":
    app = Flask(__name__)

    @app.route('/')
    def index():
        ret = '\n'.join(
            '<p><a href={}>{}</a></p>'.format('"file/' + safe(f) + '"', f)
            for f in file_paths
        )
        return f'<html><head></head><body>{ret}</body></html>', 200, {'Content-Type': 'text/html; charset=utf-8'}

    @app.route('/file/<archive>/MonoBehaviour/<filename>.json')
    def show(archive, filename):
        filename = filename.replace('$', '#') + ".json"
        print(filename)
        (path_id,) = re.match(r".* \#(\d+)\.json", filename).groups()
        with open(os.path.join(archive, 'MonoBehaviour', filename), encoding="utf-8") as f:
            parsed = json.load(f)

        fileId = FileID(archive, path_id)
        references = getReferencesHtml(fileId)
        print("get", fileId)

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

                global b64
                if b64 := x.get("serializedPublicVariablesBytesString"):
                    # Udon encoded block
                    x["serializedPublicVariablesBytesString_be"] = base64.b64decode(b64).decode("utf-16be", errors="replace")
                    x["serializedPublicVariablesBytesString_le"] = base64.b64decode(b64).decode("utf-16le", errors="replace")

                if b64 := x.get("serializedProgramBytesString"):
                    # Udon encoded block
                    x["serializedProgramBytesString_be"] = base64.b64decode(b64).decode("utf-16be", errors="replace")
                    x["serializedProgramBytesString_le"] = base64.b64decode(b64).decode("utf-16le", errors="replace")



            elif isinstance(x, list):
                for v in x:
                    traverse(v)

        traverse(parsed)
        print("traversed")
        ret = f'''<h1>{fileIdToLink(fileId)}</h1>
        {references}
        <pre style="overflow-wrap: anywhere;white-space: pre-wrap;">{json.dumps(parsed, indent=4, sort_keys=False)}</pre>''' + '<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script><script>mermaid.initialize({startOnLoad:true});</script>' + f'''        
        <div class='mermaid' style="overflow: auto;">{graphFileRefs(fileId)}</div>'''
        print("done")
        return f'<html><head></head><body>{ret}</body></html>'

    @app.route('/file/<archive>/<type>/<subtype> $<path_id>.dat')
    def showdat(archive, type, subtype, path_id):
        with open(os.path.join(archive, type, f"{subtype} #{path_id}.dat"), 'rb') as f:
            parsed = f.read()

        print(parsed)
        return f'<html><head></head><body><code style="width: 16em;display: block;overflow-wrap: anywhere;">{parsed.decode("ascii", errors="backslashreplace")}</code></body></html>'

    app.run()
