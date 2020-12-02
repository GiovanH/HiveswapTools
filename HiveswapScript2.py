import yaml
import glob
import os
from snip import loom
import asyncio
import aiofiles
import pickle
import json
import pprint
import re
import tqdm

game_root = "Act2-AssetStudio/ExportDev2"

CACHED = True

archives = {}
archives_fallback = {}

def getReference(obj):
    if isinstance(obj, dict) and 'm_PathID' in obj and 'm_FileName' in obj:
        file_name = str(obj['m_FileName'])
        path_id = str(obj['m_PathID'])
        try:
            return archives[file_name][path_id]
        except KeyError as e:
            assert path_id not in archives.get(file_name, {}).keys()
            print(repr(file_name), repr(path_id), e)
            if (file_name.startswith("level") and path_id != "0"):
                raise
            return obj
    else:
        return obj

def resolveRefs(obj, visited=[]):
    if obj in visited:
        return "(Recursive)"
    else:
        visited.append(obj)

    if isinstance(obj, list):
        return [resolveRefs(getReference(o), visited) for o in obj]
    elif isinstance(obj, dict):
        for k, v in list(obj.items()):
            # obj["@"+k] = resolveRefs(obj.pop(k))
            obj[k] = resolveRefs(getReference(v), visited)
    return obj


def dumpDeep(objs, outpath):
    dumped_objs = []
    for obj in tqdm.tqdm(objs, desc=outpath):
        try:
            dumped_objs.append(resolveRefs(obj))
        except:
            pprint.pprint(obj)
            raise

    with open(outpath, "w", encoding="utf-8") as fp:
        yaml.dump(dumped_objs, fp)


def iterArchiveFiles():
    for container, paths in archives.items():
        for p in paths:
            o = paths[p]
            o['_folderName'] = container
            o['_pathId'] = p
            yield o


async def loadJsonAsset(obj, folder_name, path_id):
    async with aiofiles.open(obj, "r", encoding="utf-8") as fp:
        o = json.loads(await fp.read())
        archives[folder_name][path_id] = o


async def loadArchives():
    global archives
    archive_cache_path = "archives.pickle"
    global CACHED

    if CACHED:
        try:
            with open(archive_cache_path, "rb") as fp:
                archives = pickle.load(fp)
        except:
            print("Cache load failed! Rebuilding")
            CACHED = False
            return await loadArchives()
    else:
        async with loom.AIOSpool(20) as spool:
            for folder in glob.glob(os.path.join(game_root, "*") + "/"):
                folder_name = os.path.split(os.path.split(folder)[0])[1]
                
                archives[folder_name] = {}
                for obj in glob.glob(os.path.join(folder, "**", "*.json")):
                    (path_id,) = re.match(r".*\#(\d+)\.json", obj).groups()
                    spool.enqueue(loadJsonAsset(obj, folder_name, path_id))
        with open(archive_cache_path, "wb") as fp:
            pickle.dump(archives, fp)

class HSMonoBehaviour():
    @property
    def keys_simple(self):
        return []

    @property
    def keys_typed(self):
        return {}
    
    def __init__(self, obj):
        super().__init__()
        self.obj = obj
        self.dict = {}

        try:
            for k in self.keys_simple:
                self.dict[k] = getReference(obj[k]),

            for k, t in self.keys_typed.items():
                # try:
                if isinstance(obj[k], list):
                    self.dict[k] = [t(getReference(o)).toDict() for o in obj[k]]
                else:
                    self.dict[k] = t(getReference(obj[k])).toDict()
                # except AttributeError:
                #     print(self, k, t)
                #     r = getReference(obj[k])
                #     print(r)
                #     i = t(r)
                #     print(type(i))
                #     print(repr(i))
                #     raise
        except KeyError:
            print(self, obj)
            raise

    def toDict(self):
        return self.dict

class HSRoot(HSMonoBehaviour):
    @property
    def keys_simple(self):
        return super().keys_simple + ['_folderName', '_pathId']

class HSAsset():
    def __init__(self, obj):
        self.obj = obj

    def toDict(self):
        # TODO
        return f"{self.obj['m_FileName']}/{self.obj['m_PathID']}"

class HSVerb(HSMonoBehaviour):
    def __init__(self, obj):
        print(obj.keys())
        super().__init__(obj)

class HSItem(HSRoot):
    @property
    def keys_simple(self):
        return super().keys_simple + ['m_Name', '_displayName', 'ItemID', 'm_Script']

    @property
    def keys_typed(self):
        o = super().keys_typed
        o.update({
            '_verbs': HSVerb,
            '_icon': HSAsset
        })
        return o

def dumpItems():
    All_Items = [HSItem(o) for o in iterArchiveFiles() if 'ItemID' in o]

    with open("Items.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDict() for i in All_Items], fp, indent=4)

async def main():
    await loadArchives()

    dumpItems()

    # Abilities = [o for o in iterArchiveFiles() if 'AbilityID' in o]
    # dumpDeep(Abilities, "Abilities.yaml")

    # Outcomes = [o for o in iterArchiveFiles() if o.get('m_Name') == "Outcome"]
    # dumpDeep(Outcomes, "Outcomes.yaml")

if __name__ == "__main__":
    asyncio.run(main())
