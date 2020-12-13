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

visited = []

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
        # if obj in visited:
        #     obj['_ERROR'] = "CIRC"
        #     return obj
        # else:
        #     visited.append(obj)
        try:
            return archives[file_name][path_id]
        except KeyError as e:
            if debugging:
                raise
            obj['_ERROR'] = "KEY"
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

def block(gen):
    for i in gen:
        yield f"  {i}"
    yield ""

# HS Classes

EXAMPLES = {}

SpeakerIdTypes = [
    "None", "JOEY",
    "XEFROS", "CHARUN", "ZEBEDE", "MARSTI", "SKYLLA", "DIEMEN", 
    "KUPRUM", "FOLYKL", "CIRAVA", "POLYPA", "BOLDIR", "AZDAJA", 
    "KONYYL", "DARAYA", "LANQUE", "LYNERA", "BRONYA", "WANSHI", 
    "MARVUS", "TEGIRI", "TIRONA", "TAGORA", "STELSA", "TYZIAS", 
    "REMELE", "ELWURD", "MALLEK", "ARDATA", "ZEBRUH", "NIHKEE", 
    "AMISIA", "GALEKH", "FOZZER", "CHIXIE", "IDARAT", "DOCKGAL",
    "LEGLESS", "VIKARE", "FIAMET", "CRIDEA", "BARZUM", "BAIZLI", 
    "CHAHUT", "KARAKO", "BARZUM_AND_BAIZLI", "BYERS", "TRIZZA"
]

BloodTypeTextColor = [
    "None", "JOEY", "JUDE", "BURGUNDY", "BRONZE", "YELLOW", 
    "OLIVE", "LIME", "RUST", "GOLD", "GREY", "JADE", "TEAL", 
    "BLUE", "INDIGO", "PURPLE", "VIOLET", "FUCHSIA"
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
    
    def __str__(self):
        return f"<{self.__class__.__name__} Name:{self.get('m_Name')} Type:{self.get('_type')} @{self.get('_folderName')}#{self.get('_pathId')}>"

    def __init__(self, obj, recursiveVerbs=False):
        super().__init__()
        self.obj = obj
        self.dict = {  
            "__pyclass": self.__class__.__name__
        }

        all_keys = set(obj.keys())
        known_keys = set(self.keys_typed.keys()).union(self.keys_simple)

        # If there are expect keys this object doesn't have
        if not (all_keys >= known_keys):
            print(obj.get("_type"), "does not map to", self.__class__.__name__)
            print("Expected", known_keys)
            print("Actual", all_keys)
            print("Missing field", known_keys.difference(all_keys))
            print()
            raise AssertionError(obj)

        try:
            k = None
            t = None
            i = None

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
                        for i, o in enumerate(obj[k])
                    ]
                    i = None
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
                all_keys.remove(k)

                self.dict[k] = getReference(obj[k])

            if all_keys:
                self.dict['__unused'] = {}
            for k in all_keys:
                self.dict['__unused'][k] = getReference(obj[k])
        
        except (KeyError, AssertionError, RecursionError) as e:
            print(e.__class__.__name__, e)
            print(self, k, t, i)
            # pprint.pprint(obj)
            print()
            raise
        except ValueError as e:
            print(type(e), e)
            print(self, k, t)
            print(list(obj.keys()))
            print()
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
                if old_example in [[], None, False] or (isinstance(old_example, dict) and old_example.get("_KeyError")):
                    if isinstance(v, list) and len(v) > 0:
                        EXAMPLES[category_name][k] = [v[0], ...]
                    else:
                        EXAMPLES[category_name][k] = v

    def toDict(self):
        flat_dict = {}
        for k, v in self.dict.items():
            if hasattr(v, 'toDict'):
                flat_dict[k] = v.toDict()
            elif isinstance(v, list):
                flat_dict[k] = [i.toDict() if hasattr(i, 'toDict') else i for i in v]
            else:
                flat_dict[k] = v

        return flat_dict

    def toDictRoot(self):
        global visited
        visited.clear()
        return self.toDict()

    def toTranscript(self):
        yield "TODO " + str(self)

class HSRoot(HSMonoBehaviour):
    @property
    def keys_simple(self):
        return super().keys_simple + ['_folderName', '_pathId', '_type']

# class HSLazy(dict):
#     def __init__(self, t, obj):
#         self.t = t
#         self.obj = obj
#         self.instance = None
#         dict.__init__(self, obj)

#     @classmethod
#     def resolve(cls, t):
#         return lambda o: cls(t, o)

#     def get(self, key):
#         if self.instance is None:
#             self.instance = self.cls(self.obj)
#         return self.instance.get(key)

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

    @property
    def title(self):
        return self.get('_displayName')
    
    def toTranscript(self):
        name = self.title

        for verb in self.get('_verbs'):
            yield from verb.toTranscript(parent_name=name)

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

    @property
    def title(self):
        return self.get('_displayName')
    
    def toTranscript(self):
        name = self.title

        for verb in self.get('_verbs'):
            yield from verb.toTranscript(parent_name=name)


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

class HSCounter(HSRoot):
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
            # 'LineMappings',
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
            'Outcome': HSOutcome.resolve
        })

    def toTranscript(self, line_num=1):
        # TODO: lots
        if self.get("IsPlayerOption"):
            # LOCALIZABLE
            yield ""
            yield "(CHOICE:)"

        # LOCALIZABLE
        yield f"{line_num} | {SpeakerIdTypes[self.get('SpeakerId')]}: {self.get('LineText')}"

        if links := self.get("LinkMappings"):
            for link in links:
                # LOCALIZABLE
                yield f"{link.get('LinkIndex')}: {link.get('MessageText')}"

        if (next_line := self.get("NextLineIndex")) != -1:
            # Localizable
            yield f"(Jump to line #{next_line})"

class HSConversationId(HSMonoBehaviour):
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
            'FinalOutcome': HSOutcome.resolve,
            'HasBeenPlayedCounter': HSCounter,
            'Lines': HSConvoLines,
            'OrphanedLines': HSConvoLines,
        })

    def toTranscript(self):
        lines = []

        # LOCALIZABLE
        yield "convo " + self.get("ConvoId").get("IdString")

        # TODO: Simplify if there aren't any jumps?
        # Maybe put transcript logic here?
        for i, line in enumerate(self.get("Lines")):
            yield from line.toTranscript(i + 1)

        return lines

class HSTarget(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'm_Script',
            'm_Name'
        ]
        return super().keys_simple + keys

class HSCondition(HSMonoBehaviour):
    # TODO: There are definitely more fields than this

    ComparisonOp = [
        "Equals",
        "DoesNotEqual",
        "LessThan",
        "GreaterThan",
    ]

    @property
    def keys_simple(self):
        keys = [
            'MustBeHero'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_counterTests': HSCounterTest,
            '_requiresAllOfTheseItems': HSItem,
            'MustHaveTargetedObjs': HSTarget,
            'MustNotHaveTargetedObjs': HSTarget
        })

    def toTranscript(self):
        lines = []

        if _requiresAllOfTheseItems := self.get('_requiresAllOfTheseItems'):
            requirements = [repr(i.get('_displayName')) for i in _requiresAllOfTheseItems]
            
            # LOCALIZABLE
            lines.append("Player must have items: " + ", ".join(requirements))

        if MustHaveTargetedObjs := self.get('MustHaveTargetedObjs'):
            requirements = [repr(i.get('m_Name')) for i in MustHaveTargetedObjs]
            
            # LOCALIZABLE
            lines.append("If targeting object(s) " + ", ".join(requirements))

        for test in self.get('_counterTests'):
            comparison = test.get('_comparison')
            value = test.get('_value')

            try:
                counter_name = test.get('_counter').get('m_Name')
            except AttributeError:
                # Counter can be null
                counter_name = "None"

            comparison_str = f"{self.ComparisonOp[comparison]}"
            # LOCALIZABLE
            lines.append(f"(If counter '{counter_name}' {comparison_str} {value})")

        if not lines:
            lines.append("Always(???)")

        yield from lines

class HSPresentOutcome(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'Outcome',  # Lazy resolution
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'TrialStateCounter': HSCounter,
        })

    def toTranscript(self):
        yield "Present outcome:"
        if counter := self.get("TrialStateCounter"):
            yield counter.get('m_Name')

        outcome = HSOutcome.resolve(self.get("Outcome"))
        if outcome:
            yield from outcome.toTranscript()
        yield ""

class HSEvidence(HSMonoBehaviour):
    @property
    def title(self):
        return self.get("TitleText") or "UNNAMED"

    @property
    def keys_simple(self):
        keys = [
            'BlockPresentCounter',
            'Descriptions',
            'ItemType',
            'TitleText',
            'm_Name'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'DefaultPresentOutcome': HSOutcome.resolve,
            'IconSprite': HSAsset,
            # 'PresentOutcomes': HSPresentOutcome,
            'UnlockOrderCounter': HSCounter,
            'DescriptionCounter': HSCounter
        })

    def toTranscript(self):
        if icon := self.get("IconSprite"):
            # LOCALIZABLE
            yield icon.toDict()

        descriptions = self.get("Descriptions")
        dcounter = self.get("DescriptionCounter")
        if dcounter:
            # LOCALIZABLE
            yield dcounter.get("m_Name")

        if len(descriptions) > 1:
            for i, d in enumerate(descriptions):
                # LOCALIZABLE
                yield f"{i+1}. {d}"
        else:
            for d in descriptions:
                # LOCALIZABLE
                yield d

        # for poutcome in self.get("PresentOutcomes"):
        #     yield from poutcome.toTranscript()

        if outcome := self.get("DefaultPresentOutcome"):
            if outcome.get("Sequence"):
                yield "When presented on other:"
                yield str(outcome.toDict())
                yield from outcome.toTranscript()

class HSTestimony(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'm_Name',
            'IncorrectEvidenceTries',
            'ShowMenuButtonDuringLoop'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'GameOverOutcome': HSOutcome.resolve,
            'IncorrectEvidenceDefaultOutcome': HSOutcome.resolve,
            'LoopConversation': HSConversation,
            'Statements': HSTestimonyStatement,
            'TestimonyActiveCounter': HSCounter,
            'TestimonyFirstPassCounter': HSCounter
        })

class HSTestimonyStatement(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'SuccessRequiresAlternateStatement',
            'HasSpecialPresentButtonOutcome',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'ActivationCondition': HSCondition,
            'AlternatePressConversation': HSConversation,
            'AlternateStatement': HSConversation,
            'AlternateStatementCounter': HSCounter,
            'PressConversation': HSConversation,
            'Statement': HSConversation,
            'SuccessEvidence': HSEvidence,

            # sequenced
            'AlternatePressOutcome': HSOutcome.resolve,
            'PressOutcome': HSOutcome.resolve,
            'SpecialPresentButtonOutcome': HSOutcome.resolve,
            'SuccessOutcome': HSOutcome.resolve
        })

class HSNPCMovement(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'Entries',
            'm_Name'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'NPCTarget': HSNPC
        })

class HSNPCState(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'Scene',
            'StartPosObject',
            'UseScenePosition',
            'Position'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Id': HSNPC,
        })

    def toTranscript(self):
        # LOCALIZABLE
        name = self.get("Id").get("m_Name")
        startpos = self.get("startpos")
        yield f"(Move {name} from {startpos})"

class HSNPC(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'm_Name',
        ]
        return super().keys_simple + keys

class HSZoomTarget(HSMonoBehaviour):
    @property
    def keys_typed(self):
        return self._keys_typed({
            'OnZoomInOutcome': HSOutcome.resolve,
            'OnZoomOutOutcome': HSOutcome.resolve
        })

class HSMovementAction(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'EndingFacingDir',
            'ForceInteractWithTarget',
            '_anim',
            '_object',
            '_targetDestination',
            '_teleportMove'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'TargetNPC': HSNPC,
            # '_heroWalkToPosition': HSTarget  # Always null or keyerror?
        })

    def toTranscript(self):
        instant = " (teleport)" if self.get("_teleportMove") else ""
        destination = self.get('_targetDestination')
        object = self.get('_object')
        # LOCALIZABLE
        yield f"Move {object} to {destination}{instant}"

class HSCounterChange(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'ChangeType',
            'Value'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'counter': HSCounter
        })

    def toTranscript(self):
        # TODO this is probably mix and match
        change_types = {
            0b0000001: "Increment",
            0b0000010: "Decrement",
            0b0000100: "HitMin",
            0b0001000: "HitMax",
            0b0010000: "Changed",
            0b0100000: "Equals",
            0b1000000: "Any"
        }

        try:
            counter_name = self.get('counter').get('m_Name')
        except AttributeError:
            # Counter can be null
            counter_name = "None"

        change_type = self.get('ChangeType')
        value = self.get('Value')

        # LOCALIZABLE
        return [f"{change_types[change_type]} counter '{counter_name}' by {value}"]


class HSHeaderMessage(HSMonoBehaviour):
    HeaderAnimType = [
        "AboveHead_FadeOut",
        "AboveHead_Alt_FadeOut",
        "Large_ExitRight",
        "Large_FadeOut",
        "AboveHero",
        "MiddlePosition",
        "ScaleUpIn_ExitRight",
        "ScaleDownIn",
        "BounceIn",
        "CrazyFlip",
        "RiseUp"
    ]

    @property
    def keys_simple(self):
        keys = [
            'DisplayText',
            'DisplayTextLine2',
            'DisplayTextLine3',
            'clearAll',
            'delay',
            'exitAnim',
            'fontColor',
            'fontColor2',
            'fontSize',
            'forceAllCaps',
            'overwritePosition',
            'overwritePositionValue',
            'positionData',
            'strokeColor1',
            'strokeColor2',
            'strokeCycleTime',
            'time'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'sfxToPlay': HSAsset,
            'colorData': HSAsset
        })

    def toTranscript(self, parent_name=None):
        # TODO
        def _transform(str):
            if self.get('forceAllCaps'):
                return str.upper()
            return str

        sfx = self.get('sfxToPlay')
        if sfx:
            # LOCALIZABLE
            yield f"(play audio '{sfx.toDict()}')"

        # LOCALIZABLE
        for linekey in ['DisplayText', 'DisplayTextLine2', 'DisplayTextLine3']:
            v = self.get(linekey)
            if v:
                yield _transform(v)
        
class HSHeroTarget(HSMonoBehaviour):
    DEBUG = True

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Conditions': HSCondition,
            'Outcome': HSOutcome.resolve,
            'Hero': HSHero
        })

    def toTranscript(self):
        if outcome := self.get("Outcome"):
            yield from outcome.toTranscript()

class HSImportTarget(HSMonoBehaviour):
    # "Import Targets" from things like verbs
    # are mostly the same but have one field different
    # This is an elaborate workaround to express that polymorphism
    # without extra code
    DEBUG = True

    field_map = {
        'Ability': HSAbility,
        'Item': HSItem,
        'TargetId': HSTarget,
        'Hero': HSHero,
    }

    @classmethod
    def resolve(cls, field):
        if field == "Hero":
            return HSHeroTarget

        ftype = cls.field_map[field]

        def _resolve(obj):
            ret = cls(obj)
            t = ftype
            k = field

            # Copied from HSMonoBehavior
            ref = getReference(obj[k])

            if ref is None:
                # References null
                ret.dict[k] = None
            else:
                ret.dict[k] = t(ref)

            return ret
        return _resolve

    @property
    def keys_simple(self):
        keys = [
            # 'CursorHighlightHotspot',
            # 'CursorHighlightOverride',
            # 'MustApproachOverride',
            # 'ImportedAnimOneShot',
            'ImportedInteractMessage',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Conditions': HSCondition,
            'Outcome': HSOutcome.resolve,
            'ImportedInteractConversation': HSConversation
        })

    def toTranscript(self):
        for message in self.get("ImportedInteractMessage", []):
            # Hero targets don't have field
            # LOCALIZABLE
            yield f"{message}"

        if conversation := self.get("ImportedInteractConversation"):
            yield from conversation.toTranscript()

        if outcome := self.get("Outcome"):
            yield from outcome.toTranscript()


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
        # TODO: These _targets are wrappers
        # with "imported" values
        return self._keys_typed({
            '_abilityTargets': HSImportTarget.resolve("Ability"),
            '_itemTargets': HSImportTarget.resolve("Item"),
            '_heroTargets': HSHeroTarget,
            '_interactableTargets': HSImportTarget.resolve("TargetId"),
            '_activationConditions': HSCondition,
            '_defaultTargetFail': HSOutcome.resolve,
            '_outcome': HSOutcome.resolve,
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
                assert not list(target.toTranscript())

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
        yield from lines

# Outcomes

class HSOutcome(HSRoot):
    @classmethod
    def resolve(cls, obj):
        outcome_class_map = {
            "OutcomeActionAnimation": HSOutcomeAnimation,
            "OutcomeActionConversation": HSOutcomeConversation,
            "OutcomeActionCounters": HSOutcomeCounter,
            "OutcomeActionCutscene": HSOutcomeCutscene,
            "OutcomeActionChittr": HSOutcomeChittr,
            "OutcomeActionInventory": HSOutcomeInventory,
            "OutcomeActionMovement": HSOutcomeMovement,
            "OutcomeActionUtility": HSOutcomeUtility,
            "OutcomeActionMessage": HSOutcomeMessage,
            "OutcomeActionZoom": HSOutcomeZoom,
            "OutcomeActionChangeScene": HSOutcomeChangeScene,
            "OutcomeActionChangeHero": HSOutcomeChangeHero,
            "OutcomeActionUI": HSOutcomeUI,
            "OutcomeActionSound": HSOutcomeSound,
            "OutcomeOnStateEnter": HSOutcomeOnStateEnter,
            "OutcomeSwitchCameraTarget": HSOutcomeSwitchCameraTarget,
            "OutcomeActionVFX": HSOutcomeVFX,
            "OutcomeActionFade": HSOutcomeFade,
            "OutcomeActionNPCGoal": HSOutcomeNPCGoal,
            "OutcomeActionTrial": HSOutcomeTrial,
            "OutcomeActionPolynav": HSOutcomePolynav,
            "Outcome": HSOutcomeSequence
        }

        obj_type = obj.get("_type")
        if obj_type is None and 'Sequence' in obj:
            # Coherse, debug?
            return HSOutcomeWrapper(obj)

        cls_match = outcome_class_map[obj_type]
        return cls_match(obj)

    @property
    def keys_simple(self):
        keys = [
            'm_Name'
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        # Children cannot use this function
        if self.__class__ != HSOutcome:
            raise NotImplementedError(self.__class__)

        if self.get('_type') != "Outcome":
            raise NotImplementedError(self.get('_type'))

        yield str(self)

class HSOutcomeWrapper(HSMonoBehaviour):
    @property
    def keys_typed(self):
        return self._keys_typed({
            'Sequence': HSOutcomeCanvas
        })

    def toTranscript(self):
        # TODO: Order?
        if seq := self.get("Sequence"):
            yield from seq.toTranscript()

class HSOutcomeSequence(HSMonoBehaviour):
    # DEBUG = True

    @property
    def keys_simple(self):
        keys = [
            'StartDelay'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'ActivateCondition': HSCondition,
            'ActionsList': HSOutcome.resolve
        })

    def toTranscript(self):
        # Actual outcome sequence
        condition = list(self.get("ActivateCondition").toTranscript())
        if condition:
            yield from condition

            # TODO: Ordering?
            for outcome in self.get("ActionsList"):
                yield from block(outcome.toTranscript())

        else:
            for outcome in self.get("ActionsList"):
                yield from outcome.toTranscript()


class HSOutcomePolynav(HSMonoBehaviour):
    pass
    # semantically uninteresting

class HSOutcomeTrial(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'AllowMultiplePresent',
            'AllowPresentOnCourtRecordView',
            'ClearTyziasHints',
            'CourtRecordView',
            'EndCameraLock',
            'EndTestimony',
            'EndTrialZoom',
            'ForcePresentOnCourtRecordView',
            'ForceSetTestimonyIndex',
            'HideConvoImage',
            'HideCourtHintButton',
            'HideCourtMenuButton',
            'HideCourtRecord',
            'LockCameraOnNPC',
            'ResetTestimonyPressButtons',
            'RestoreCourtRecord',
            'ShowCourtDefenseButtons',
            'ShowCourtHintButton',
            'ShowCourtMenuButton',
            'ShowCourtRecord',
            'ShowLastItemPresented',
            'ShowTyziasTestimonyHint',
            'TrialZoomTarget',
            'UpdateTestimonyIndicators',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'CenteredConvoImageToShow': HSEvidence,
            'ConvoImageToShow': HSEvidence,
            'TyziasTrialItemHints': HSEvidence,
            'Testimony': HSTestimony
        })

    def toTranscript(self):
        # TODO
        # LOCALIZABLE
        yield


class HSOutcomeVFX(HSMonoBehaviour):
    LineVFXTypes = [
        "None",
        "Flash",
        "HoldIt",
        "TakeThat",
        "Objection",
        "Flash_Minor",
        "Long_Flash"
    ]

    @property
    def keys_simple(self):
        keys = [
            'LineVFXToTrigger',
            'VFXName',
            'VFXStartDelay',
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        # Localizable
        yield f"VFX {self.LineVFXTypes[self.get('LineVFXToTrigger')]} ({self.get('VFXName')})"

class HSOutcomeNPCGoal(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'm_Name',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Sequence': HSNPCMovement,
            'NPCStateUpdates': HSNPCState
        })

    def toTranscript(self):
        for update in self.get("NPCStateUpdates"):
            # Localizable
            yield from update.toTranscript()

class HSOutcomeFade(HSMonoBehaviour):
    FadeType = [
        "FadeIn",
        "FadeOut",
        "WakeUp"
    ]

    @property
    def keys_simple(self):
        keys = [
            'FadeDuration',
            'TypeOfFade',
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        # Localizable
        ftype = self.get("TypeOfFade")
        yield f"Fade {self.FadeType[ftype]} {self.get('FadeDuration')}s"

class HSOutcomeOnStateEnter(HSRoot):
    @property
    def keys_typed(self):
        return self._keys_typed({
            'Outcome': HSOutcome.resolve
        })

    def toTranscript(self):
        yield from self.get('Outcome').toTranscript()

class HSOutcomeSwitchCameraTarget(HSMonoBehaviour):
    # there's a bunch of other camera stuff we can ignore

    @property
    def keys_simple(self):
        keys = [
            'CameraPanTarget',
            'AttachToHero',
            'SnapToHero',
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        # LOCALIZABLE
        yield f"(Move camera to {self.get('CameraPanTarget')})"

class HSOutcomeCanvas(HSRoot):
    @property
    def keys_simple(self):
        keys = [
            'm_Name'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'nodes': HSOutcomeSequence
        })

    @property
    def title(self):
        return f"{self.get('_folderName')} OutcomeCanvas#{self.get('_pathId')}"

    def toTranscript(self):
        # LOCALIZABLE
        if self.get('nodes') is None:
            print(self.toDict())
            raise AssertionError
        # TODO: Order?
        for node in self.get('nodes')[::-1]:
            yield from node.toTranscript()


class HSOutcomeChangeScene(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'Fade',
            'ForceSceneChange',
            'GoToScene',
            'OverrideNewSceneFadeIn',
            'ShowHUDAfterFade'
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        verb = "Fade" if self.get('Fade') else "Cut"
        # LOCALIZABLE
        yield f"({verb} to scene '{self.get('GoToScene')}')"

class HSOutcomeChangeHero(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'AddHeroFacing',
            'AddHeroSpawnLocation',
            'AddHeroToParty',
            'ClearFloorMarkerOverride',
            'DisableHero',
            'DisableSwitching',
            'EnableSwitching',
            'FrontFloorMarkerOverride',
            'RearFloorMarkerOverride',
            'RemoveHeroFromParty',
            'SwitchHero',
            'UnlockHero',
            'GoToScene'
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        # LOCALIZABLE
        # TODO
        yield

class HSOutcomeZoom(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'EndActiveZoom',
            'PopupZoom',
            'ZoomTargetName',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'ZoomTarget': HSZoomTarget
        })

    def toTranscript(self):
        # LOCALIABLE
        yield "TODO ZOOM"

class HSOutcomeMovement(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'ActivateClickCatcherForMove',
            'FollowerFacingDir',
            'HeroFacingDir',
            'LockFollowerFacing',
            'LockFollowerMovement',
            'PausePlayerActionsSec',
            'UnlockFollowerFacing',
            'UnlockFollowerMovement',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'MovementActions': HSMovementAction
        })

    def toTranscript(self):
        for action in self.get("MovementActions"):
            yield from action.toTranscript()

class HSOutcomeSound(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'BlockWorldSounds',
            'EnableWorldSounds',
            'LocalSoundPlay',
            'LocalSoundStop',
            'OnSoundEndCancel',
            'OnWorldSoundEnd',
            'TargetSoundPlayer',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'WorldSoundPlay': HSAsset,
            'WorldSoundStop': HSAsset
        })

    def toTranscript(self):
        play_file = self.get("WorldSoundPlay")
        if play_file:
            # LOCALIZABLE
            yield f"(play audio '{play_file.toDict()}')"

class HSOutcomeMessage(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'Messages',
            'interactionData',
            'loadFromVerb'
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        for message in self.get("Messages"):
            # LOCALIZABLE
            yield f"{message}"

class HSOutcomeAnimation(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'AnimParams',
            'Animation',
            'WaitForAnimFinish'
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        for param in self.get('AnimParams'):
            obj_name = param.get('_objName')
            param_name = param.get('_paramName')
            anim_type = param.get('_type')
            value = param.get('value')
            # LOCALIZABLE
            yield f"Animation: {obj_name} {param_name}, {anim_type=} {value=}"

class HSOutcomeUtility(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            # 'ConditionalConversations',
            # 'EndActiveConversation',
            # 'LineVFXToPlay',
            # 'TriggerPartyConversation',
            'ClearCheckpointSave',
            'CreateCheckpointSave',
            'DoFinalSave',
            'EnableNewGamePlusTitle',
            'EventOutcome',
            'ForceAutosave',
            'LoadCheckpointSave',
            'ResumeAutosaveTimer',
            'StopAutosaveTimer',
            'UnlockAchievement',
            'UpdateHeroDataPosition',
        ]
        return super().keys_simple + keys

    def toTranscript(self):

        if self.get("DoFinalSave"):
            # LOCALIZABLE
            yield "(Save game FINAL)"

        if self.get("ForceAutosave"):
            # LOCALIZABLE
            yield "(Autosave)"

        if ach := self.get("UnlockAchievement"):
            # LOCALIZABLE
            yield f"(Unlock Achievement: '{ach}')"

        assert not self.get("LineVFXToPlay")
        assert not self.get('TriggerPartyConversation')
        # assert not self.get('ClearCheckpointSave')
        # assert not self.get('CreateCheckpointSave')
        # assert not self.get('EnableNewGamePlusTitle')
        # assert not self.get('LoadCheckpointSave')
        # assert not self.get('ResumeAutosaveTimer')
        # assert not self.get('StopAutosaveTimer')
        # assert not self.get('UpdateHeroDataPosition')

        assert self.get('EventOutcome') == {
            "m_PersistentCalls": {
                "m_Calls": []
            }
        }

class HSOutcomeConversation(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'ConditionalConversations',
            'EndActiveConversation',
            'LineVFXToPlay',
            'TriggerPartyConversation'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'ConversationToTrigger': HSConversation
        })

    def toTranscript(self):
        assert not self.get("ConditionalConversations")
        
        assert not self.get("ConditionalConversations")

        if self.get("EndActiveConversation"):
            # LOCALIZABLE
            yield "(End conversation)"

        if trigger_convo := self.get("ConversationToTrigger"):
            yield from trigger_convo.toTranscript()

class HSOutcomeCounter(HSMonoBehaviour):
    @property
    def keys_typed(self):
        return self._keys_typed({
            'counterChanges': HSCounterChange
        })

    def toTranscript(self):
        lines = []
        for change in self.get("counterChanges"):
            yield from change.toTranscript()
        return lines

class HSOutcomeCutscene(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'ClipToPlay',
            'CoverScreenWhileLoading',
            'NewPauseOnLastFrameSetting',
            'OverridePauseOnLastFrame',
            'OverrideStopMusicFlag'
        ]
        return super().keys_simple + keys

    def toTranscript(self):
        # LOCALIZABLE
        yield f"(play cutscene '{self.get('ClipToPlay')}')"

class HSOutcomeChittr(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'HideChittr',
            'ShowChittr',
            'SetActiveProfile',
            'ShowAllTextImmediately',
            'UpdateChittrHistory'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'ChittrConversation': HSConversation
        })

    def toTranscript(self, parent_name=None):
        if self.get('ShowChittr'):
            # LOCALIZABLE
            yield "(Opens Chittr)"

        if self.get('SetActiveProfile'):
            # TODO resolve profile number
            profile = self.get('SetActiveProfile')
            # LOCALIZABLE
            yield f"(Switches to Chittr profile {profile})"

        if self.get('HideChittr'):
            # LOCALIZABLE
            yield "(Hides Chittr)"


class HSOutcomeInventory(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'AbilitiesToAdd',
            'AbilitiesToRemove',
            'DevicesToAdd',
            'DevicesToRemove',
            'HeroTarget',
            'TrialItemsToUnlock',
        ]
        return super().keys_simple + keys
    
    @property
    def keys_typed(self):
        return self._keys_typed({
            'ItemsToAdd': HSItem,
            'ItemsToRemove': HSItem
        })

    def toTranscript(self):
        for ability in self.get("AbilitiesToRemove"):
            ability_name = ability.get("_displayName")
            # LOCALIZABLE
            yield f"Skill '{ability_name}' removed"

        for ability in self.get("AbilitiesToAdd"):
            ability_name = ability.get("_displayName")
            # LOCALIZABLE
            yield f"Skill '{ability_name}' learned"

        for device in self.get("DevicesToRemove"):
            device_name = device.get("_displayName")
            # LOCALIZABLE
            yield f"'{device_name}' removed from inventory"

        for device in self.get("DevicesToAdd"):
            device_name = device.get("_displayName")
            # LOCALIZABLE
            yield f"'{device_name}' added to inventory"

        for item in self.get("ItemsToRemove"):
            item_name = item.get("_displayName")
            # LOCALIZABLE
            yield f"'{item_name}' removed from inventory"

        for item in self.get("ItemsToAdd"):
            item_name = item.get("_displayName")
            # LOCALIZABLE
            yield f"'{item_name}' added to inventory"


class HSOutcomeUI(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'HideChalkboard',
            'HideCurrentConvoLine',
            'HideHUD',
            'HideHUDComplete',
            'ShowChalkboard',
            'ShowHUD'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'HeaderMessages': HSHeaderMessage
        })

    def toTranscript(self, parent_name=None):
        # LOCALIZABLE
        for message in self.get('HeaderMessages'):
            yield from message.toTranscript()

        for key, line in [
            ('HideChalkboard', "(Hide Chalkboard)"),
            ('HideCurrentConvoLine', "(Hide conversation)"),
            ('HideHUD', "(Hide HUD)"),
            ('HideHUDComplete', "(Hide HUD Complete"),
            ('ShowChalkboard', "(Show Chalkboard)"),
            ('ShowHUD', "(Show HUD)")
        ]:
            if self.get(key):
                # LOCALIZABLE
                yield line

# Operations

def dumpItems():
    All_Items = [HSItem(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'ItemID' in o]

    with open("Items.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Items], fp, indent=4)

    with open("ItemsTranscript.md", "w", encoding="utf-8") as fp:
        for item in All_Items:
            try:
                fp.write(f"# {item.title}\n\n")
                fp.write("\n".join(item.toTranscript()))
                fp.write("\n\n")
            except:
                pprint.pprint(item.toTranscript())
                raise

def dumpEvidence():
    All_Evidence = [HSEvidence(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'PresentOutcomes' in o]

    with open("Evidence.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Evidence], fp, indent=4)

    with open("EvidenceTranscript.md", "w", encoding="utf-8") as fp:
        for item in All_Evidence:
            try:
                fp.write(f"# {item.title}\n\n")
                fp.write("\n".join(item.toTranscript()))
                fp.write("\n\n")
            except:
                pprint.pprint(list(item.toTranscript()))
                raise

def dumpAbilities():
    All_Abilities = [HSAbility(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'AbilityID' in o]

    with open("Abilities.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Abilities], fp, indent=4)

    with open("AbilitiesTranscript.md", "w", encoding="utf-8") as fp:
        for ability in All_Abilities:
            try:
                fp.write(f"# {ability.title}\n\n")
                fp.write("\n".join(ability.toTranscript()))
                fp.write("\n\n")
            except:
                pprint.pprint(ability.toTranscript())
                raise

def dumpOutcomes():
    All_Outcomes = [HSOutcomeCanvas(o) for o in iterArchiveFiles() if o.get("_type") == "OutcomeCanvas"]
    All_Outcomes.sort(key=lambda o: (o.get('_folderName'), o.get('_pathId')))

    with open("Outcomes.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Outcomes], fp, indent=4)

    with open("OutcomesTranscript.md", "w", encoding="utf-8") as fp:
        for outcome in All_Outcomes:
            try:
                fp.write(f"# {outcome.title}\n\n")
                fp.write("\n".join(outcome.toTranscript()))
                fp.write("\n\n")
            except:
                pprint.pprint(outcome.toTranscript())
                raise

async def main():
    await loadArchives()

    try:
        dumpEvidence()
        dumpOutcomes()
        dumpItems()
        dumpAbilities()
    finally:
        pprint.pprint(EXAMPLES, compact=True)

    # Abilities = [o for o in iterArchiveFiles() if 'AbilityID' in o]
    # dumpDeep(Abilities, "Abilities.yaml")

    # Outcomes = [o for o in iterArchiveFiles() if o.get('m_Name') == "Outcome"]
    # dumpDeep(Outcomes, "Outcomes.yaml")

if __name__ == "__main__":
    asyncio.run(main())
