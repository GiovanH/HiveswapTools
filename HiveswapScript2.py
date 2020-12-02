import yaml
import glob
import os
import asyncio
import aiofiles
import pickle
import json
import pprint
import re
import collections

try:
    from snip.loom import AIOSpool
except ImportError as e:
    print(e)

    class AIOSpool:
        def __init__(self, quota=8, *args):
            self.queue = []

        def enqueue(self, target):
            self.queue.append(target)

        async def __aenter__(self):
            return self

        async def __aexit__(self, type, value, traceback):
            await asyncio.gather(*self.queue)

try:
    from tqdm import tqdm
except ImportError:
    print("tqdm not installed, using dumb iterator")

    def tqdm(iterable, *args):
        yield from iterable

game_root = "Act2-AssetStudio/ExportDev2"

CACHED = True

archives = {}
archives_fallback = {}

# Utilities and loading

def getReference(obj):
    if isinstance(obj, dict) and 'm_PathID' in obj and 'm_FileName' in obj:
        file_name = str(obj['m_FileName'])
        path_id = str(obj['m_PathID'])
        if obj['m_PathID'] == 0 and obj['m_FileID'] == 0:
            return None
        try:
            return archives[file_name][path_id]
        except KeyError as e:
            assert path_id not in archives.get(file_name, {}).keys()
            # print(type(e), file_name, path_id, e)
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


# def dumpDeep(objs, outpath):
#     dumped_objs = []
#     for obj in tqdm.tqdm(objs, desc=outpath):
#         try:
#             dumped_objs.append(resolveRefs(obj))
#         except:
#             pprint.pprint(obj)
#             raise

#     with open(outpath, "w", encoding="utf-8") as fp:
#         yaml.dump(dumped_objs, fp)


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
        async with AIOSpool(20) as spool:
            for folder in glob.glob(os.path.join(game_root, "*") + "/"):
                folder_name = os.path.split(os.path.split(folder)[0])[1]
                
                archives[folder_name] = {}
                for obj in glob.glob(os.path.join(folder, "**", "*.json")):
                    (path_id,) = re.match(r".*\#(\d+)\.json", obj).groups()
                    spool.enqueue(loadJsonAsset(obj, folder_name, path_id))
        with open(archive_cache_path, "wb") as fp:
            pickle.dump(archives, fp)

# HS Classes

EXAMPLES = {}

class HSMonoBehaviour():
    DEBUG = False

    @property
    def keys_simple(self):
        return []

    @property
    def keys_typed(self):
        return {}

    def _keys_typed(self, keys):
        try:
            o = super().keys_typed
        except AttributeError:
            o = {}
        o.update(keys)
        return o
    
    def __init__(self, obj, recursiveVerbs=False):
        super().__init__()
        self.obj = obj
        self.dict = {}

        try:
            k = None
            t = None

            for k in self.keys_simple:
                self.dict[k] = getReference(obj[k]),

            for k, t in self.keys_typed.items():
                if k not in obj:
                    continue

                if k == '_verbs' and not recursiveVerbs:
                    continue

                if isinstance(obj[k], list):
                    self.dict[k] = [
                        t(o).toDict() if o is not None else None
                        for o in obj[k]
                    ]
                else:
                    ref = getReference(obj[k])

                    if ref is None:
                        # References null
                        self.dict[k] = None
                    else:
                        self.dict[k] = t(ref).toDict()
        except KeyError:
            print(self, obj)
            raise
        except RecursionError:
            print(self, k, t)
            raise

        if self.DEBUG:
            for k, v in obj.items():
                category_name = self.__class__.__name__
                if (k in self.keys_simple) or (k in self.keys_typed):
                    category_name += " (known)"

                # print(category_name, k, v)
                if isinstance(v, dict) and v.get('m_FileName', 'Sentinal') is None:
                    v = None

                if category_name not in EXAMPLES:
                    EXAMPLES[category_name] = {}

                old_example = EXAMPLES[category_name].get(k, [])
                if old_example in [[], None, False]:
                    if isinstance(v, list) and len(v) > 0:
                        EXAMPLES[category_name][k] = [v[0], ...]
                    else:
                        EXAMPLES[category_name][k] = v

    def toDict(self):
        return self.dict

class HSRoot(HSMonoBehaviour):
    @property
    def keys_simple(self):
        return super().keys_simple + ['_folderName', '_pathId']

class HSAsset():
    def __init__(self, obj, asset_type="*"):
        self.obj = obj

        archive_name = self.obj['m_FileName']
        path_id = self.obj['m_PathID']

        matches = glob.glob(os.path.join(game_root, archive_name, asset_type, f"*#{path_id}.*"))
        assert len(matches) == 1, matches
        self.path = matches[0].replace("\\", "/")

    @classmethod
    def typed(cls, arg):
        return lambda obj: cls(obj, asset_type=arg)

    def toDict(self):
        return self.path

class HSAbility(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'm_Name', '_displayName', 'AbilityID', 'm_Script'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_verbs': HSVerb,
            '_icon': HSAsset.typed("Sprite")
        })
    pass

class HSCounter(HSRoot):
    DEBUG = True

    @property
    def keys_simple(self):
        keys = [
            '_dataScope',
            '_guid',
            '_maxValue',
            '_minValue',
            '_startValue',
            '_wraps',
            'm_Name'
        ]
        return super().keys_simple + keys

class HSCounterTest(HSMonoBehaviour):
    DEBUG = True

    @property
    def keys_simple(self):
        keys = [
            '_comparison',
            '_value'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_counter': HSCounter
        })

class HSTarget(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'Conditions'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Outcome': HSOutcome,
            'Ability': HSAbility
        })

class HSCondition(HSMonoBehaviour):
    DEBUG = True
    # TODO: There are definitely more fields than this

    @property
    def keys_simple(self):
        keys = [
            'MustBeHero'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_counterTests': HSCounterTest
        })

class HSOutcome(HSMonoBehaviour):
    @property
    def keys_typed(self):
        return self._keys_typed({
            'Sequence': HSOutcomeSequence
        })

class HSOutcomeSequence(HSMonoBehaviour):
    DEBUG = True
    pass


class HSVerb(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            '_name',
            '_cursorOverride',
            '_mustApproach'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_abilityTargets': HSTarget,
            '_heroTargets': HSTarget,
            '_itemTargets': HSTarget,
            '_interactableTargets': HSTarget,
            '_activationConditions': HSCondition,
            '_defaultTargetFail': HSOutcome,
            '_outcome': HSOutcome,
        })

class HSItem(HSRoot):
    @property
    def keys_simple(self):
        keys = [
            'm_Name', '_displayName', 'ItemID', 'm_Script'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_verbs': HSVerb,
            '_icon': HSAsset.typed("Sprite")
        })

# Operations

def dumpItems():
    All_Items = [HSItem(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'ItemID' in o]

    with open("Items.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDict() for i in All_Items], fp, indent=4)

def dumpAbilities():
    All_Abilities = [HSAbility(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'AbilityID' in o]

    with open("Abilities.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDict() for i in All_Abilities], fp, indent=4)

async def main():
    await loadArchives()

    dumpItems()
    dumpAbilities()

    pprint.pprint(EXAMPLES, compact=True)

    # Abilities = [o for o in iterArchiveFiles() if 'AbilityID' in o]
    # dumpDeep(Abilities, "Abilities.yaml")

    # Outcomes = [o for o in iterArchiveFiles() if o.get('m_Name') == "Outcome"]
    # dumpDeep(Outcomes, "Outcomes.yaml")

if __name__ == "__main__":
    asyncio.run(main())
