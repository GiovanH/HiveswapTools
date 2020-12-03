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
    debugging = False
    if isinstance(obj, dict) and 'm_PathID' in obj and 'm_FileName' in obj:
        file_name = str(obj['m_FileName'])
        path_id = str(obj['m_PathID'])

        if path_id == "10186":
            debugging = True

        if obj['m_PathID'] == 0 and obj['m_FileID'] == 0:
            return None
        try:
            return archives[file_name][path_id]
        except KeyError as e:
            if debugging:
                raise
            obj['_KeyError'] = True
            return obj
    else:
        return obj

# def resolveRefs(obj, visited=[]):
#     if obj in visited:
#         return "(Recursive)"
#     else:
#         visited.append(obj)

#     if isinstance(obj, list):
#         return [resolveRefs(getReference(o), visited) for o in obj]
#     elif isinstance(obj, dict):
#         for k, v in list(obj.items()):
#             # obj["@"+k] = resolveRefs(obj.pop(k))
#             obj[k] = resolveRefs(getReference(v), visited)
#     return obj


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
            yield o


async def loadJsonAsset(obj, folder_name, path_id, utype):
    async with aiofiles.open(obj, "r", encoding="utf-8") as fp:
        o = json.loads(await fp.read())
        o['_folderName'] = folder_name
        o['_pathId'] = path_id
        o['_type'] = utype
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
                    (utype, path_id,) = re.match(r".*\\(.*) \#(\d+)\.json", obj).groups()
                    spool.enqueue(loadJsonAsset(obj, folder_name, path_id, utype))
        with open(archive_cache_path, "wb") as fp:
            pickle.dump(archives, fp)

# HS Classes

EXAMPLES = {}

SpeakerIdTypes = [
    "NONE", "JOEY", 
    "XEFROS", "CHARUN", "ZEBEDE", "MARSTI", "SKYLLA", "DIEMEN", 
    "KUPRUM", "FOLYKL", "CIRAVA", "POLYPA", "BOLDIR", "AZDAJA", 
    "KONYYL", "DARAYA", "LANQUE", "LYNERA", "BRONYA", "WANSHI", 
    "STELSA", "TYZIAS", "REMELE", "ELWURD", "MALLEK", "ARDATA", 
    "ZEBRUH", "NIHKEE", "AMISIA", "GALEKH", "FOZZER", "CHIXIE", 
    "IDARAT", "DOCKGAL", "LEGLESS", "VIKARE", "FIAMET", "CRIDEA", 
    "BARZUM", "BAIZLI", "CHAHUT", "KARAKO", "BARZUM_AND_BAIZLI", 
    "BYERS", "TRIZZA"
]

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

    def get(self, *args, **kwargs):
        return self.dict.get(*args, **kwargs)
    
    def __init__(self, obj, recursiveVerbs=False):
        super().__init__()
        self.obj = obj
        self.dict = {  
            "__pyclass": self.__class__.__name__
        }

        all_keys = list(obj.keys())

        try:
            k = None
            t = None

            for k, t in self.keys_typed.items():
                if k not in obj:
                    continue
                all_keys.remove(k)

                if k == '_verbs' and not recursiveVerbs:
                    self.dict[k] = "[OMMITTED]"
                    continue

                if isinstance(obj[k], list):
                    self.dict[k] = [
                        t(getReference(o)) if o else o
                        for o in obj[k]
                    ]
                else:
                    ref = getReference(obj[k])

                    if ref is None:
                        # References null
                        self.dict[k] = None
                    else:
                        self.dict[k] = t(ref)

            for k in self.keys_simple:
                if k not in obj:
                    continue
                try:
                    all_keys.remove(k)
                except:
                    print(all_keys)
                    print(k)
                self.dict[k] = getReference(obj[k])

            if all_keys:
                self.dict['__unused'] = {}
            for k in all_keys:
                self.dict['__unused'][k] = getReference(obj[k])
        
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
        return {
            k: (
                v.toDict() if hasattr(v, 'toDict')
                else 
                (
                    [i.toDict() for i in v if hasattr(i, 'toDict')]
                    if isinstance(v, list) else v
                )
            )
            for k, v in 
            self.dict.items()
        }

class HSRoot(HSMonoBehaviour):
    @property
    def keys_simple(self):
        return super().keys_simple + ['_folderName', '_pathId', '_type']

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

    def toTranscript(self):
        name = self.get('_displayName')
        verbs = self.get('_verbs')

        lines = []
        lines.append(f"# {name}\n")

        for verb in verbs:
            lines += verb.toTranscript(parent_name=name)

        return lines

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

class HSHero(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'Hero',
            '_prefab',
            '_startScene',
            '_startingAbilities',
            '_startingDevices',
            '_startingEquipment',
            'm_Name'
        ]
        return super().keys_simple + keys

class HSConvoLines(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'DisplaySpeed',
            'EmotionIndex',
            'EndsConversation',
            'HideConversationWindowForLine',
            'HideLineUntilOutcomeFinishes',
            'IsPlayerOption',
            'LineText',
            'LineVFX',
            'LineMappings',
            'LoopLineIndex',
            'NextLineIndex',
            'SpeakerId',
            'TextColorOverride',
            'LinkMappings'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Condition': HSCondition,
            'OptionConvoId': HSConversationId,
            'Outcome': HSOutcome
        })

    def toTranscript(self):
        lines = []

        # TODO: Convo formatting
        line = f"{SpeakerIdTypes[self.get('SpeakerId')]}: {self.get('LineText')}"
        lines.append(line)

        return lines

class HSConversationId(HSMonoBehaviour):
    DEBUG = True
    @property
    def keys_simple(self):
        keys = [
            'Area',
            'Branches',
            'Character',
            'Conversation',
            'IdString',
            'MajorPlot',
            'MinorPlot'
        ]
        return super().keys_simple + keys

class HSConversation(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'AutoPlayLines',
            'ConversationUIOverride',
            'ConvoCameraSizeOverride',
            'IsPlayerOnly',
            'IsRefresher',
            'DestroyConversationAfterSceneChange',
            'm_Name'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'ConvoId': HSConversationId,
            'FinalOutcome': HSOutcome,
            'HasBeenPlayedCounter': HSCounter,
            'Lines': HSConvoLines,
            'OrphanedLines': HSConvoLines,
        })

    def toTranscript(self):
        lines = []

        for line in self.get("Lines"):
            lines += line.toTranscript()

        return lines

class HSTarget(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'CursorHighlightHotspot',
            'CursorHighlightOverride',
            'MustApproachOverride',
            'ImportedAnimOneShot',
            'ImportedInteractMessage',
            'm_Script',
            'm_Name'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Conditions': HSCondition,
            'Outcome': HSOutcome,
            'Ability': HSAbility,
            'Item': HSItem,
            'TargetId': HSTarget,
            'Hero': HSHero,
            'ImportedInteractConversation': HSConversation
        })

    def toTranscript(self):
        lines = []

        for message in self.get("ImportedInteractMessage", []):
            # Hero targets don't have field
            lines.append(f"Narrator: {message}")

        conversation = self.get("ImportedInteractConversation")
        if conversation:
            lines += conversation.toTranscript()

        return lines

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

# TODO: Map outcomes to subclasses based on
# _type field
class HSOutcome(HSRoot):
    DEBUG = True

    @property
    def keys_simple(self):
        keys = [
            'm_Name'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Sequence': HSOutcomeSequence,
            'ActivateCondition': HSCondition,
            'ActionsList': HSOutcome
        })

    def toTranscript(self):
        if self.get('Sequence'):
            return self.get('Sequence').toTranscript()
        else:
            return []

class HSOutcomeSequence(HSMonoBehaviour):
    DEBUG = True

    @property
    def keys_simple(self):
        keys = [
            'm_Name'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'nodes': HSOutcome
        })

    def toTranscript(self):
        lines = []
        for node in self.get('nodes'):
            lines += node.toTranscript()

        return lines

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
            '_itemTargets': HSTarget,
            '_heroTargets': HSTarget,
            '_interactableTargets': HSTarget,
            '_activationConditions': HSCondition,
            '_defaultTargetFail': HSOutcome,
            '_outcome': HSOutcome,
        })

    def toTranscript(self, parent_name=None):
        lines = []
        verb_clause = f"{self.get('_name')} {parent_name}" if self.get('_name') != parent_name else parent_name

        # Determine "default message"
        message_counter = collections.defaultdict(int)

        all_targets = [
            *self.get('_abilityTargets'),
            *self.get('_itemTargets'),
            *self.get('_heroTargets'),
            # *self.get('_interactableTargets')
        ]
        for target in all_targets:
            transcript = "\n".join(target.toTranscript())
            message_counter[transcript] += 1

        try:
            default_message = sorted(message_counter.items(), key=lambda i: i[1])[-1][0]
        except IndexError:
            default_message = None

        # Iterate through all targets
        for target in self.get('_abilityTargets'):
            target_name = target.get('Ability').get('_displayName')
            lines.append(f"## {verb_clause} with {target_name}\n")

            lines += target.toTranscript()
            lines.append("")

        for target in self.get('_itemTargets'):
            # Some target Item references are null; deleted items?
            try:
                target_name = target.get('Item').get('_displayName')
            except AttributeError:
                target_name = "[deleted item]"

            # If the item is deleted and the transcript is the default, skip it
            target_transcript = target.toTranscript()
            if target_name == "[deleted item]" and "\n".join(target_transcript) == default_message:
                continue
            else:
                lines.append(f"## {verb_clause} with {target_name}\n")
                lines += target_transcript
                lines.append("")

        for target in self.get('_heroTargets'):
            target_name = target.get('Hero').get('m_Name')
            transcript = target.toTranscript()
            # Only a couple instances of this (joey tap dance), both null

            if transcript:
                lines.append(f"## {verb_clause} with {target_name}\n")

                lines += transcript
                lines.append("")

        # TODO interactable targets
        for target in self.get('_interactableTargets'):
            try:
                target_name = target.get('TargetId').get('m_Name')
            except:
                # Target is null
                assert not target.toTranscript()

            transcript = target.toTranscript()
            # Only a couple instances of this (joey tap dance), both null

            if transcript:
                lines.append(f"## {verb_clause} with {target_name}\n")

                lines += transcript
                lines.append("")


        outcome = self.get('_outcome')
        if outcome:
            sub_transcript = outcome.toTranscript()
            if sub_transcript:
                lines.append(f"## {verb_clause} default outcome\n")

                lines += sub_transcript
                lines.append("")

        defaultTargetFail = self.get('_defaultTargetFail')
        if defaultTargetFail:
            sub_transcript = defaultTargetFail.toTranscript()
            if sub_transcript:
                lines.append(f"## {verb_clause} default outcome\n")

                lines += sub_transcript
                lines.append("")

        if not lines:
            # If there's no body, record debugging info
            lines.append(f"## {verb_clause} (Empty)\n")
            lines.append(pprint.pformat(self.dict) + "\n")
        return lines

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

    def toTranscript(self):
        name = self.get('_displayName')
        verbs = self.get('_verbs')

        lines = []
        lines.append(f"# {name}\n")

        for verb in verbs:
            lines += verb.toTranscript(parent_name=name)

        return lines

# Operations

def dumpItems():
    All_Items = [HSItem(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'ItemID' in o]

    with open("Items.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDict() for i in All_Items], fp, indent=4)

    with open("ItemsTranscript.md", "w", encoding="utf-8") as fp:
        for item in All_Items:
            try:
                fp.write("\n".join(item.toTranscript()))
                fp.write("\n")
            except:
                pprint.pprint(item.toTranscript())
                raise

def dumpAbilities():
    All_Abilities = [HSAbility(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'AbilityID' in o]

    with open("Abilities.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDict() for i in All_Abilities], fp, indent=4)

    with open("AbilitiesTranscript.md", "w", encoding="utf-8") as fp:
        for ability in All_Abilities:
            try:
                fp.write("\n".join(ability.toTranscript()))
                fp.write("\n")
            except:
                pprint.pprint(ability.toTranscript())
                raise

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
