import glob
import os
import asyncio
import aiofiles
import pickle
import json
import pprint
import re
import collections
from urllib.parse import quote_plus, quote
from functools import lru_cache

# TODO: Group items/abilities by TARGET too, not just ITEM
# that'll be easier to sort into gameplay order probably

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
outcomes_seen = set()

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

def block(gen, kind="block"):
    yield f"<div class='{kind}'>"
    for i in gen:
        yield f"    {i}"
    yield "</div>"

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

HeroNum = [
    "Joey",
    "Jude",
    "Xefros"
]

SceneNameInBuildSettings = {
    "level0": "Global Module",
    "level1": "Splashes",
    "level2": "Start Menu",
    "level3": "002 Mountains Exterior",
    "level4": "002 Mountains Interior",
    "level5": "003 Plains Interior",
    "level6": "003 Plains Exterior",
    "level7": "Static Credits",
    "level8": "003 No Spray Game Over",
    "level9": "003 Bee Dance Minigame",
    "level10": "005 Rust-Bronze Car",
    "level11": "002 Swim Game Over",
    "level12": "006 Yellow-Olive Car",
    "level13": "001 Trainstop Cafe",
    "level14": "007 Jade-Teal Car",
    "level15": "008 Cerulean Car",
    "level16": "008 Indigo Car",
    "level17": "004 Train Station Ticket Area",
    "level18": "004 Train Station Boarding ",
    "level19": "006 Yellow-Olive Gangway",
    "level20": "005 Rust-Bronze Gangway",
    "level21": "008 Ardata Game Over",
    "level22": "008 Indigo Gangway",
    "level23": "009 Clown Car",
    "level24": "010 Engine Room Gangway",
    "level25": "010 Engine Room",
    "level26": "007 Bronya Trial Game Over",
    "level27": "007 Tirona Trial Game Over",
    "level28": "007 Tegiri Trial Game Over",
    "level29": "007 Trial Minigame",
    "level30": "007 Lynera Trial Game Over",
    "level31": "010 Drone Look GameOver",
    "level32": "010 Track Switch GameOver",
    "level33": "006 Azdaja Strife",
    "level34": "007 Lanque Trial Game Over",
    "level35": "007 Jade-Teal Gangway",
    "level36": "010 Final Scene",
}

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
        return f"{self.__class__.__name__} Name:{self.get('m_Name')} Type:{self.get('_type')} @{self.get('_folderName')}#{self.get('_pathId')}"

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

    def toTranscriptBody(self):
        yield "TODO " + str(self)

class HSRoot(HSMonoBehaviour):
    @property
    def keys_simple(self):
        return super().keys_simple + ['_folderName', '_pathId', '_type']

    @property
    def key(self):
        assert self.get('_folderName')
        return (self.get('_folderName'), self.get('_pathId'))
    

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
    
    def toTranscriptBody(self):
        name = self.title

        if icon := self.get("_icon"):
            # LOCALIZABLE
            yield f"<img class='item_icon' src='{quote(icon.toDict())}' title='{icon.toDict()}'></img>"

        for verb in self.get('_verbs'):
            yield from verb.toTranscriptBody(parent_name=name)

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
    
    def toTranscriptBody(self):
        name = self.title

        if icon := self.get("_icon"):
            # LOCALIZABLE
            yield f"<img class='item_icon' src='{quote(icon.toDict())}' title='{icon.toDict()}'></img>"

        for verb in self.get('_verbs'):
            yield from verb.toTranscriptBody(parent_name=name)


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

    @property
    def isbool(self):
        return self.get("_minValue") == 0 and self.get("_maxValue") == 1
    

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

class HSConversationSpeaker(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'SpeakerId',
            'SpeakerColor',
            'TextColor',
            'AlternativeSpaceCharacter'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'NameLearnedCounter': HSCounter
        })

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

    def toTranscriptBody(self):
        convo_lines = []

        has_jump = any(
            line.get("NextLineIndex") != -1
            for line in self.get("Lines")
        )

        # Start item
        yield f"<div class='convo' id='{self.get('ConvoId').get('IdString')}'>"

        if has_jump:
            yield "<ol>"

        for line_num, line in enumerate(self.get("Lines")):
            # TODO: lots
            try:
                speaker = ConversationSpeakers[line.get('SpeakerId')]
                color_id = line.get("TextColorOverride") or speaker.get("SpeakerColor")
                
                color = BloodTypeTextColor[color_id]
            except KeyError:
                color = f"BLOOD{line.get('SpeakerId')}"

            tag_name = "li" if has_jump and not line.get("IsPlayerOption") else "p"
            yield f"<{tag_name} class='{color}'>"

            if line.get("IsPlayerOption"):
                # LOCALIZABLE
                yield ""
                yield "(CHOICE)"

            # LOCALIZABLE
            yield f"<span class='speakername'>{SpeakerIdTypes[line.get('SpeakerId')]}</span> {line.get('LineText')}"

            # Link mappings for galekh
            if links := line.get("LinkMappings"):
                for link in links:
                    # LOCALIZABLE
                    yield f"<span class='footnote'>{link.get('LinkIndex')}: {link.get('MessageText')}</span>"

            # "Jump" notifier
            if (next_line := line.get("NextLineIndex")) != -1:
                # Localizable
                yield f"<span class='jump'>(Jump to line #{next_line-1})</span>"
            
            # End item
            yield f"</{tag_name}>"
        yield from convo_lines  # block(convo_lines)

        if has_jump:
            yield "</ol>"
        yield "</div>"

        if final_outcome := self.get("FinalOutcome"):
            yield from final_outcome.toTranscriptBody()

class HSTarget(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'm_Script',
            'm_Name'
        ]
        return super().keys_simple + keys


class HSTriggerVolume(HSRoot):
    DEBUG = True

    @property
    def keys_simple(self):
        keys = [
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'OnEnterSequence': HSOutcomeWrapper,
            'OnExitSequence': HSOutcomeWrapper,
        })

    @property
    def title(self):
        return SceneNameInBuildSettings[self.get("_folderName")] + " TriggerVolume " + self.get("_pathId")

    def toTranscriptBody(self):
        if onEnter := self.get("OnEnterSequence"):
            if body_lines := list(onEnter.toTranscriptBody()):
                yield "<h2>On Enter</h2>"
                yield from block(body_lines)

        if onExit := self.get("onExitSequence"):
            if body_lines := list(onExit.toTranscriptBody()):
                yield "<h2>On Exit</h2>"
                yield from block(body_lines)

            

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
            'MustBeHero',
            'LastScene'
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

    def toTranscriptBody(self):
        lines = []

        if last_scene := self.get('LastScene'):
            # LOCALIZABLE
            lines.append("came from scene " + last_scene)

        if (required_hero := self.get('MustBeHero')) != -1:
            # LOCALIZABLE
            lines.append("current hero is " + HeroNum[required_hero])

        if _requiresAllOfTheseItems := self.get('_requiresAllOfTheseItems'):
            requirements = [repr(i.get('_displayName')) for i in _requiresAllOfTheseItems]
            
            # LOCALIZABLE
            lines.append("player has items: " + ", ".join(requirements))

        if MustHaveTargetedObjs := self.get('MustHaveTargetedObjs'):
            requirements = [repr(i.get('m_Name')) for i in MustHaveTargetedObjs]
            
            # LOCALIZABLE
            lines.append("targeting object(s) " + ", ".join(requirements))

        for test in self.get('_counterTests'):
            comparison = test.get('_comparison')
            value = test.get('_value')

            try:
                counter_name = test.get('_counter').get('m_Name')
            except AttributeError:
                # Counter can be null
                counter_name = "None"

            comparison_str = f"{self.ComparisonOp[comparison]} {value}"
            if test.get('_counter') and test.get('_counter').isbool:
                if comparison_str == "Equals 0":
                    comparison_str = "is False"
                if comparison_str == "Equals 1":
                    comparison_str = "is True"
            # LOCALIZABLE
            lines.append(f"'{counter_name}' {comparison_str}")

        # LOCALIZABLE
        if lines:
            yield "<span class='condition'>If " + " AND ".join(lines) + "</span>"

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

    def toTranscriptBody(self):
        yield "Present outcome:"
        if counter := self.get("TrialStateCounter"):
            yield counter.get('m_Name')

        outcome = HSOutcome.resolve(self.get("Outcome"))
        if outcome:
            yield from outcome.toTranscriptBody()
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

    def toTranscriptBody(self):
        if icon := self.get("IconSprite"):
            # LOCALIZABLE
            yield f"<img class='evidence_icon' src='{quote(icon.toDict())}' title='{icon.toDict()}'></img>"

        descriptions = self.get("Descriptions")
        dcounter = self.get("DescriptionCounter")
        if dcounter:
            # LOCALIZABLE
            yield "<span class='evidence_counter_switch'>" + dcounter.get("m_Name") + "</span>"

        yield "<p class='evidence_descriptions'>"
        if len(descriptions) > 1:
            yield "<ol class='evidence_descriptions'>"
            for i, d in enumerate(descriptions):
                # LOCALIZABLE
                yield f"<li>{d}</li>"
            yield "</ol>"
        else:
            for d in descriptions:
                # LOCALIZABLE
                yield d
        yield "</p>"

        # for poutcome in self.get("PresentOutcomes"):
        #     yield from poutcome.toTranscriptBody()

        if outcome := self.get("DefaultPresentOutcome"):
            if outcome.get("Sequence"):
                yield "When presented on other:"
                yield str(outcome.toDict())
                yield from outcome.toTranscriptBody()

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

    def toTranscriptBody(self):
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

    def toTranscriptBody(self):
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

    def toTranscriptBody(self):
        # this is probably mix and match
        # update: it is not
        change_types = {
            0b0000001: "Increment",
            0b0000010: "Decrement",
            0b0000100: "HitMin",
            0b0001000: "HitMax",
            0b0010000: "Changed",
            0b0100000: "Equals",
            0b1000000: "Any"
        }
        # if it's Increment, Decrement, value is always 0? ignored?

        try:
            counter_name = self.get('counter').get('m_Name')

            if self.get('counter').isbool:
                change_types.update({
                    0b0000001: "Set",
                    0b0000010: "Unset",
                })

        except AttributeError:
            # Counter can be null
            counter_name = "None"

        change_type = self.get('ChangeType')
        value = self.get('Value')

        # LOCALIZABLE
        if change_types[change_type] == "Equals":
            yield f"<span class='sys'>{change_types[change_type]} counter '{counter_name}' to {value}</span>"
        else:
            yield f"<span class='sys'>{change_types[change_type]} counter '{counter_name}'</span>"


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

    def toTranscriptBody(self, parent_name=None):
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
        for linekey, color_k in [
            ('DisplayText', "fontColor"),
            ('DisplayTextLine2', "fontColor2"),
            ('DisplayTextLine3', "fontColor")
        ]:
            color_d = self.get(color_k)
            color = f"rgb{color_d['r']*255, color_d['g']*255, color_d['b']*255}"
            v = f"<span class='headermessage' style='color: {color};'>" + self.get(linekey) + "</span>"
            if v:
                yield _transform(v)
        
class HSInteractable(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            '_displayName',

        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_activeCondition': HSCondition,
            '_targetId': HSTarget,
            '_verbs': HSVerb
        })

    @property
    def title(self):
        if target := self.get("_targetId"):
            return target.get("m_Name", "UNNAMED TARGET") 
        return self.get("m_Name", "UNNAMED NO TARGET")

    def toTranscriptBody(self):
        for v in self.get("_verbs"):
            yield from v.toTranscriptBody(parent_name=self.title)

class HSHeroTarget(HSMonoBehaviour):
    @property
    def keys_typed(self):
        return self._keys_typed({
            'Conditions': HSCondition,
            'Outcome': HSOutcome.resolve,
            'Hero': HSHero
        })

    def toTranscriptBody(self):
        if outcome := self.get("Outcome"):
            yield from outcome.toTranscriptBody()

class HSSpawnPoint(HSMonoBehaviour):
    DEBUG = True

    @property
    def keys_simple(self):
        keys = [
            'PreviousScene',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'Outcome': HSOutcome.resolve
        })

class HSHeroConversationData(HSMonoBehaviour):
    def __init__(self, obj):
        super().__init__(obj, recursiveVerbs=True)

    @property
    def keys_simple(self):
        keys = [
            'm_Name',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_verbs': HSVerb
        })

class HSSceneManager(HSRoot):
    @property
    def keys_simple(self):
        keys = [
            'debugLastRoom',
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            '_arrivalOutcome': HSOutcome.resolve,
            '_heroSpawnPoints': HSSpawnPoint,
            # '_localCounterChangeOutcomes': HSCounterChange,  
            # TODO ugggh it's not QUITE a counterchange AND it has outcomes
            'HeroConversationData': HSHeroConversationData,
            'PreArrivalOutcome': HSOutcome.resolve,
        })

    @property
    def title(self):
        return "SceneManager " + SceneNameInBuildSettings[self.get("_folderName")]
    
    def toTranscriptBody(self):
        outcome = self.get("PreArrivalOutcome")
        if body := list(outcome.toTranscriptBody()):
            yield "<h2>Before arrival</h2>"
            yield from body

        outcome = self.get("_arrivalOutcome")
        if body := list(outcome.toTranscriptBody()):
            yield "<h2>On arrival</h2>"
            yield from body

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

            # Copied from HSMonoBehaviour
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

    def toTranscriptBody(self):

        if conversation := self.get("ImportedInteractConversation"):
            yield from conversation.toTranscriptBody()

        if outcome := self.get("Outcome"):
            yield from outcome.toTranscriptBody()

        for message in self.get("ImportedInteractMessage", []):
            # Hero targets don't have field
            # LOCALIZABLE
            yield "<span class='condition always'>Default (imported)</span>"
            yield from block([f"<p class='message'>{message}</p>"], "conditionalbody")


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

    def toTranscriptBody(self, parent_name=None):
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
            transcript = "\n".join(target.toTranscriptBody())
            message_counter[transcript] += 1

        try:
            default_message = sorted(message_counter.items(), key=lambda i: i[1])[-1][0]
        except IndexError:
            default_message = None

        # Iterate through all targets
        for target in self.get('_abilityTargets'):
            # LOCALIZABLE
            target_name = target.get('Ability').get('_displayName')
            lines.append(f"<h2 class='verb abilitytarget'>{verb_clause} with {target_name}</h2>\n")

            lines += target.toTranscriptBody()
            lines.append("")

        for target in self.get('_itemTargets'):
            # Some target Item references are null; deleted items?
            try:
                target_name = target.get('Item').get('_displayName')
            except AttributeError:
                target_name = "[deleted item]"

            # If the item is deleted and the transcript is the default, skip it
            target_transcript = target.toTranscriptBody()
            if target_name == "[deleted item]" and "\n".join(target_transcript) == default_message:
                continue
            else:
                lines.append(f"<h2 class='verb itemtarget'>{verb_clause} with {target_name}</h2>\n")
                lines += target_transcript
                lines.append("")

        for target in self.get('_heroTargets'):
            target_name = target.get('Hero').get('m_Name')
            transcript = target.toTranscriptBody()
            # Only a couple instances of this (joey tap dance), both null

            if transcript:
                lines.append(f"<h2 class='verb herotarget'>{verb_clause} with {target_name}</h2>\n")

                lines += transcript
                lines.append("")

        # TODO interactable targets
        for target in self.get('_interactableTargets'):
            try:
                target_name = target.get('TargetId').get('m_Name')
            except:
                # Target is null
                assert not list(target.toTranscriptBody())

            transcript = target.toTranscriptBody()
            # Only a couple instances of this (joey tap dance), both null

            if transcript:
                lines.append(f"<h2 class='verb interactabletarget'>{verb_clause} with {target_name}</h2>\n")

                lines += transcript
                lines.append("")

        outcome = self.get('_outcome')
        if outcome:
            sub_transcript = outcome.toTranscriptBody()
            if sub_transcript:
                lines.append(f"<h2 class='verb notarget'>{verb_clause}</h2>\n")

                lines += sub_transcript
                lines.append("")

        defaultTargetFail = self.get('_defaultTargetFail')
        if defaultTargetFail:
            sub_transcript = defaultTargetFail.toTranscriptBody()
            if list(sub_transcript):
                lines.append(f"<h2 class='verb notarget fail'>{verb_clause}</h2>\n")

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

    def toTranscriptBody(self):
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

    @property
    def title(self):
        return self.get("Sequence").title

    def toTranscriptBody(self):
        if seq := self.get("Sequence"):
            yield f"<!-- {self} -->"
            yield from seq.toTranscriptBody()

class HSNodeEditorNode(HSRoot):
    @property
    def keys_simple(self):
        keys = [
            'connections',
            'calculationBlockade',
            'typeID',
            'body'
        ]
        return super().keys_simple + keys

class HSOutcomeSequence(HSRoot):
    # DEBUG = True

    @property
    def keys_simple(self):
        keys = [
            'StartDelay',
            'Inputs'
        ]
        return super().keys_simple + keys

    @property
    def keys_typed(self):
        return self._keys_typed({
            'ActivateCondition': HSCondition,
            'ActionsList': HSOutcome.resolve,
            'Outputs': HSNodeEditorNode
        })

    def __str__(self):
        return f"{self.__class__.__name__} @{self.get('_folderName')}#{self.get('_pathId')}"

    def toTranscriptBody(self):
        # Actual outcome sequence
        # yield f"<span class='sys'>{self}</span>"

        condition = list(self.get("ActivateCondition").toTranscriptBody())
        
        condition = [f"<span class='sys'>{self}</span>"] + condition

        if condition:

            # TODO: Ordering?
            block_lines = []
            for outcome in self.get("ActionsList"):
                block_lines += list(outcome.toTranscriptBody())

            if block_lines:
                yield from condition
                yield from block(block_lines, "conditionalbody")
            else:
                # TODO: Empty?
                pass

        else:
            for outcome in self.get("ActionsList"):
                yield from outcome.toTranscriptBody()


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

    # def toTranscriptBody(self):
    #     # TODO
    #     # LOCALIZABLE


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

    def toTranscriptBody(self):
        # Localizable
        yield f"<span class='sys'>VFX {self.LineVFXTypes[self.get('LineVFXToTrigger')]} ({self.get('VFXName')})</span>"

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

    def toTranscriptBody(self):
        for update in self.get("NPCStateUpdates"):
            # Localizable
            yield from update.toTranscriptBody()

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

    def toTranscriptBody(self):
        # Localizable
        ftype = self.get("TypeOfFade")
        yield f"Fade {self.FadeType[ftype]} {self.get('FadeDuration')}s"

class HSOutcomeOnStateEnter(HSRoot):
    @property
    def keys_typed(self):
        return self._keys_typed({
            'Outcome': HSOutcome.resolve
        })

    @property
    def title(self):
        return self.get('Outcome').title
    
    def toTranscriptBody(self):
        yield from self.get('Outcome').toTranscriptBody()

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

    def toTranscriptBody(self):
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

    def toTranscriptBody(self):
        global outcomes_seen
        outcomes_seen.add(self.key)

        yield f"<!-- {self} -->"
        # LOCALIZABLE
        if self.get('nodes') is None:
            print(self.toDict())
            raise AssertionError

        # TODO: Complex input/output system determines order of execution

        # Raw test
        # yield "<div class='mermaid'>graph TD"

        # for node in self.get('nodes'):

        #     node_key = f"{node.get('_type')}.{node.get('_folderName')}.{node.get('_pathId')}"

        #     yield f"  %% Node {node_key}"
        #     yield f"  {node_key}([{node_key}])"

        #     for input_node in node.get("Inputs"):
        #         in_key = f"con_{input_node.get('m_FileName')}.{input_node.get('m_PathID')}"

        #         yield f"  %% - Input {in_key}"
        #         yield f"  {in_key}-->{node_key}"

        #     if not node.get("Inputs"):
        #         yield f"  START-->{node_key}"

        #     for output_node in node.get("Outputs"):
        #         out_key = f"con_{output_node.get('_folderName')}.{output_node.get('_pathId')}"

        #         yield f"  %% - Output {out_key}"
        #         yield f"  {node_key}-->{out_key}"

        #         for output_connection in output_node.get("connections"):
        #             con_key = f"con_{output_connection.get('m_FileName')}.{output_connection.get('m_PathID')}"

        #             yield f"  %%   - Connection {con_key}"
        #             yield f"  {out_key}---{con_key}"

        # yield "</div>"

        # Actual implementation
        adj_list = collections.defaultdict(list)
        nodes_by_key = {}
            # (node.get('_folderName'), node.get('_pathId')): node
            # for node in self.get('nodes')
        # }

        for node in self.get('nodes'):

            node_key = f"{node.get('_type')}.{node.get('_folderName')}.{node.get('_pathId')}"
            nodes_by_key[node_key] = node

            for input_node in node.get("Inputs"):
                in_key = f"con_{input_node.get('m_FileName')}.{input_node.get('m_PathID')}"
                adj_list[in_key].append(node_key)

            if not node.get("Inputs"):
                adj_list['START'].append(node_key)

            for output_node in node.get("Outputs"):
                out_key = f"con_{output_node.get('_folderName')}.{output_node.get('_pathId')}"
                adj_list[node_key].append(out_key)

                for output_connection in output_node.get("connections"):
                    con_key = f"con_{output_connection.get('m_FileName')}.{output_connection.get('m_PathID')}"
                    adj_list[out_key].append(con_key)
                    # adj_list[con_key].append(node_key)

        def _pruneCons(rootkey='START'):
            # TODO: Not sure which is more efficient

            # Bottom-up parsing
            for dstkey in adj_list[rootkey]:
                if dstkey.startswith("con_"):
                    # Connection
                    adj_list[rootkey].remove(dstkey)
                    adj_list[rootkey] += adj_list[dstkey]
                    _pruneCons(rootkey)  # changed adj_list[rootkey] mid-iteration
                _pruneCons(dstkey)

            # for conkey in adj_list:
            #     if conkey.startswith("con_"):
            #         for srckey in adj_list:
            #             if conkey in adj_list[srckey]:
            #                 # srckey connects to con
            #                 adj_list[srckey] += adj_list[conkey]
            #                 adj_list[srckey].remove(conkey)

        def _traverseNodeGraph(rootkey='START', visited=None):
            if visited is None:
                visited = list()
            for dstkey in adj_list[rootkey]:
                pathkey = (rootkey, dstkey)
                if pathkey in visited:
                    continue
                else:
                    visited.append(pathkey)
                    yield pathkey
                    yield from _traverseNodeGraph(dstkey, visited)

        _pruneCons()

        yield "<div class='mermaid'>graph LR"
        for srckey, dstkey in _traverseNodeGraph():
            yield f"  {srckey}-->{dstkey}"
        yield "</div>"

        # Note: This is *a* valid order, not actually the correct one.
        # No good way to easily express simultaneous events in a transcript

        # Maybe try to put "long" events later? urgh

        for starter_key in adj_list['START']:
            yield "<div class='nodebody'>"
            yield from nodes_by_key[starter_key].toTranscriptBody()
            for prevkey, nodekey in _traverseNodeGraph(rootkey=starter_key):
                yield from nodes_by_key[nodekey].toTranscriptBody()
            yield "</div>"

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

    def toTranscriptBody(self):
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

    # def toTranscriptBody(self):
    #     # LOCALIZABLE
    #     # TODO
        

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

    def toTranscriptBody(self):
        return
        yield

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

    def toTranscriptBody(self):
        for action in self.get("MovementActions"):
            yield from action.toTranscriptBody()

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

    def toTranscriptBody(self):
        play_file = self.get("WorldSoundPlay")
        if play_file:
            # LOCALIZABLE
            yield f"<span class='sys'>(play audio '{play_file.toDict()}')</span>"

class HSOutcomeMessage(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'Messages',
            'interactionData',
            'loadFromVerb'
        ]
        return super().keys_simple + keys

    def toTranscriptBody(self):
        for message in self.get("Messages"):
            # LOCALIZABLE
            yield f"<p class='message'>{message}</p>"

class HSOutcomeAnimation(HSMonoBehaviour):
    @property
    def keys_simple(self):
        keys = [
            'AnimParams',
            'Animation',
            'WaitForAnimFinish'
        ]
        return super().keys_simple + keys

    def toTranscriptBody(self):
        for param in self.get('AnimParams'):
            obj_name = param.get('_objName')
            param_name = param.get('_paramName')
            anim_type = param.get('_type')
            value = param.get('value')
            # LOCALIZABLE
            yield f"<span class='sys'>Animation: {obj_name} {param_name}, {anim_type=} {value=}</span>"

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

    def toTranscriptBody(self):

        if self.get("DoFinalSave"):
            # LOCALIZABLE
            yield "<span class='sys'>(Save game FINAL)</span>"

        if self.get("ForceAutosave"):
            # LOCALIZABLE
            yield "<span class='sys'>(Autosave)</span>"

        if ach := self.get("UnlockAchievement"):
            # LOCALIZABLE
            yield f"<span class='sys'>(Unlock Achievement: <b>{ach}</b>)</span>"

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

    def toTranscriptBody(self):
        assert not self.get("ConditionalConversations")
        
        assert not self.get("ConditionalConversations")

        if self.get("EndActiveConversation"):
            # LOCALIZABLE
            yield "(End conversation)"

        if trigger_convo := self.get("ConversationToTrigger"):
            yield from trigger_convo.toTranscriptBody()

class HSOutcomeCounter(HSMonoBehaviour):
    @property
    def keys_typed(self):
        return self._keys_typed({
            'counterChanges': HSCounterChange
        })

    def toTranscriptBody(self):
        lines = []
        for change in self.get("counterChanges"):
            yield from change.toTranscriptBody()
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

    def toTranscriptBody(self):
        # LOCALIZABLE
        yield f"<span class='sys'>(play cutscene '{self.get('ClipToPlay')}')</span>"
        yield f"<video class='cutscene' controls src='StreamingAssets/{self.get('ClipToPlay')}'></video>"


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

    def toTranscriptBody(self, parent_name=None):
        if self.get('ShowChittr'):
            # LOCALIZABLE
            yield "(Opens Chittr)"

        if self.get('SetActiveProfile'):
            # TODO resolve profile number
            profile = self.get('SetActiveProfile')
            # LOCALIZABLE
            yield f"(Switches to Chittr profile {profile})"
            # TODO: Insert chittr conversation here?

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

    def toTranscriptBody(self):
        for ability in self.get("AbilitiesToRemove"):
            ability_name = ability.get("_displayName")
            # LOCALIZABLE
            yield f"<span class='sys'>Skill '{ability_name}' removed</span>"

        for ability in self.get("AbilitiesToAdd"):
            ability_name = ability.get("_displayName")
            # LOCALIZABLE
            yield f"<span class='sys'>Skill '{ability_name}' learned</span>"

        for device in self.get("DevicesToRemove"):
            device_name = device.get("_displayName")
            # LOCALIZABLE
            yield f"<span class='sys'>'{device_name}' removed from inventory</span>"

        for device in self.get("DevicesToAdd"):
            device_name = device.get("_displayName")
            # LOCALIZABLE
            yield f"<span class='sys'>'{device_name}' added to inventory</span>"

        for item in self.get("ItemsToRemove"):
            item_name = item.get("_displayName")
            # LOCALIZABLE
            yield f"<span class='sys'>'{item_name}' removed from inventory</span>"

        for item in self.get("ItemsToAdd"):
            item_name = item.get("_displayName")
            # LOCALIZABLE
            yield f"<span class='sys'>'{item_name}' added to inventory</span>"


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

    def toTranscriptBody(self, parent_name=None):
        # LOCALIZABLE
        for message in self.get('HeaderMessages'):
            yield from message.toTranscriptBody()

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

HTML_META = """
<link rel="stylesheet" href="transcript.css"></link>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>
    var config = {
        startOnLoad:true,
        htmlLabels:true,
        flowchart:{
            useMaxWidth:false,
        }
    };
    mermaid.initialize(config);
</script>
"""

# Calculate reference graph

def ddictlist():
    # module level function, picklable
    return collections.defaultdict(list)

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


FileID = collections.namedtuple("FileID", ["fileName", "pathId"])
file_paths = sorted(glob.glob(game_root + "/*/MonoBehaviour/*"))

referencesFrom = collections.defaultdict(list)
referencedBy = collections.defaultdict(list)
referencedAs = collections.defaultdict(ddictlist)

reference_cache_filepath = "scriptrefs.pickle"
try:
    with open(reference_cache_filepath, "rb") as fp:
        (referencesFrom, referencedBy, referencedAs) = pickle.load(fp)
    print("Loaded cached references")
except (FileNotFoundError, EOFError):
    print("Building references...")
    for path in tqdm(file_paths):
        (folder_name, path_id) = re.match(r".+?([^\/]*)\/[^\/]+\/[^\/]+\#(\d+)\.json", path.replace("\\", "/")).groups()
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
        print(repr(file_id))
        return '<p>No references to this file</p>'

    return "<p>Referenced by:</p><ul>\n" + "\n".join(["<li>" + fileIdToName(ref) + " as " + ", ".join(referencedAs[file_id][ref]) + "</li>" for ref in set(referencedBy[file_id])]) + "</ul>"

@lru_cache(10000)
def fileIdToName(ref):
    target_glob = None
    try:
        assert ref.fileName is not None
        target_glob = os.path.join(game_root, ref.fileName, "*", f"*#{ref.pathId}.*")
        targetNames = glob.glob(target_glob)

        assert len(targetNames) == 1
        targetName = targetNames[0].replace('\\', '/')
        return targetName
    except (AssertionError, IndexError):
        print(target_glob)
        print(ref)
        return f"Unknown! ({ref.fileName}/{ref.pathId})"

# Operations

def dumpItems():
    print("Dumping items")

    All_Items = [HSItem(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'ItemID' in o]
    All_Items.sort(key=lambda o: o.title)

    with open("Items.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Items], fp, indent=4)

    with open("ItemsTranscript.html", "w", encoding="utf-8") as fp:
        fp.write(HTML_META)
        for item in All_Items:
            try:
                fp.write(f"<h1>{item.title}\n\n")
                fp.write("\n".join(item.toTranscriptBody()))
                fp.write("\n\n")
            except Exception:
                pprint.pprint(item.toTranscriptBody())
                raise

def dumpEvidence():
    print("Dumping evidence")

    All_Evidence = [HSEvidence(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'PresentOutcomes' in o]

    with open("Evidence.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Evidence], fp, indent=4)

    with open("EvidenceTranscript.html", "w", encoding="utf-8") as fp:
        fp.write(HTML_META)
        for item in All_Evidence:
            try:
                fp.write(f"<h1>{item.title}</h1>\n\n")
                fp.write("\n".join(item.toTranscriptBody()))
                fp.write("\n\n")
            except Exception:
                pprint.pprint(list(item.toTranscriptBody()))
                raise

def dumpAbilities():
    print("Dumping abilities")

    All_Abilities = [HSAbility(o, recursiveVerbs=True) for o in iterArchiveFiles() if 'AbilityID' in o]

    with open("Abilities.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Abilities], fp, indent=4)

    with open("AbilitiesTranscript.html", "w", encoding="utf-8") as fp:
        fp.write(HTML_META)
        for ability in All_Abilities:
            try:
                fp.write(f"<h1>{ability.title}</h1>\n\n")
                fp.write("\n".join(ability.toTranscriptBody()))
                fp.write("\n\n")
            except Exception:
                pprint.pprint(ability.toTranscriptBody())
                raise

def dumpInteractables():
    print("Dumping interactables")

    All_Interactables = [HSInteractable(o, recursiveVerbs=True) for o in iterArchiveFiles() if o.get("_type") == "Interactable"]
    All_Interactables.sort(key=lambda o: o.title)

    with open("Interactables.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Interactables], fp, indent=4)

    with open("InteractablesTranscript.html", "w", encoding="utf-8") as fp:
        fp.write(HTML_META)
        for interactable in All_Interactables:
            try:
                fp.write(f"<h1>{interactable.title}</h1>\n\n")
                fp.write("\n".join(interactable.toTranscriptBody()))
                fp.write("\n\n")
            except Exception:
                pprint.pprint(list(interactable.toTranscriptBody()))
                raise

def dumpScenes():
    print("Dumping scenes")

    All_Scenes = [HSSceneManager(o, recursiveVerbs=True) for o in iterArchiveFiles() if o.get("_type") == "SceneManager"]
    All_Scenes.sort(key=lambda o: o.title)

    with open("Scenes.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Scenes], fp, indent=4)

    with open("ScenesTranscript.html", "w", encoding="utf-8") as fp:
        fp.write(HTML_META)
        for scenemgr in All_Scenes:
            try:
                fp.write(f"<h1>{scenemgr.title}</h1>\n\n")
                fp.write("\n".join(scenemgr.toTranscriptBody()))
                fp.write("\n\n")
            except Exception:
                pprint.pprint(list(scenemgr.toTranscriptBody()))
                raise

def dumpAnimOutcomes():
    print("Dumping animation outcomes")

    All_OnEnter = [HSOutcomeOnStateEnter(o) for o in iterArchiveFiles() if o.get("_type") == "OutcomeOnStateEnter"]
    All_OnEnter.sort(key=lambda o: (o.get('_folderName'), o.get('_pathId')))

    with open("OutcomesOnEnter.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_OnEnter], fp, indent=4)

    with open("OutcomesOnEnterTranscript.html", "w", encoding="utf-8") as fp:
        fp.write(HTML_META)
        for outcome in All_OnEnter:
            try:
                fp.write(f"<h1>{outcome.title}</h1>\n\n")
                fp.write("\n".join(outcome.toTranscriptBody()))
                fp.write("\n\n")
            except Exception:
                pprint.pprint(list(outcome.toTranscriptBody()))
                raise

def dumpTriggerVolumes():
    print("Dumping trigger volumes")

    All_TriggerVolumes = [HSTriggerVolume(o) for o in iterArchiveFiles() if o.get("_type") == "TriggerVolume"]
    All_TriggerVolumes.sort(key=lambda o: (o.get('_folderName'), o.get('_pathId')))

    with open("TriggerVolumes.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_TriggerVolumes], fp, indent=4)

    with open("TriggerVolumes.html", "w", encoding="utf-8") as fp:
        fp.write(HTML_META)
        for trigger in All_TriggerVolumes:
            try:
                fp.write(f"<h1>{trigger.title}</h1>\n\n")
                fp.write("\n".join(trigger.toTranscriptBody()))
                fp.write("\n\n")
            except Exception:
                pprint.pprint(list(trigger.toTranscriptBody()))
                raise

def dumpOutcomes():
    print("Dumping other outcomes")

    All_Outcomes = [HSOutcomeCanvas(o) for o in iterArchiveFiles() if o.get("_type") == "OutcomeCanvas"]
    All_Outcomes = [o for o in All_Outcomes if o.key not in outcomes_seen]
    All_Outcomes.sort(key=lambda o: (o.get('_folderName'), o.get('_pathId')))

    with open("Outcomes.json", "w", encoding="utf-8") as fp:
        json.dump([i.toDictRoot() for i in All_Outcomes], fp, indent=4)

    with open("OutcomesTranscript.html", "w", encoding="utf-8") as fp:
        fp.write(HTML_META)
        for outcome in All_Outcomes:
            try:
                file_id = FileID(outcome.get('_folderName'), outcome.get('_pathId'))
                fp.write(f"<h1>{outcome.title}</h1>\n\n")
                fp.write(getReferencesHtml(file_id) + "\n")
                fp.write("\n".join(outcome.toTranscriptBody()))
                fp.write("\n\n")
            except Exception:
                pprint.pprint(list(outcome.toTranscriptBody()))
                raise

async def main():
    await loadArchives()

    global ConversationSpeakers
    # this is literally how the game does it, sorry
    ConversationSpeakers = {
        o.get("SpeakerId"): HSConversationSpeaker(o)
        for o in iterArchiveFiles()
        if o.get("_type") == "ConversationSpeaker"
    }

    try:
        dumpTriggerVolumes()
        dumpScenes()
        dumpItems()
        dumpAbilities()
        dumpEvidence()
        dumpInteractables()
        dumpTriggerVolumes()
        dumpAnimOutcomes()
        dumpOutcomes()
    finally:
        pprint.pprint(EXAMPLES, compact=True)

    # Abilities = [o for o in iterArchiveFiles() if 'AbilityID' in o]
    # dumpDeep(Abilities, "Abilities.yaml")

    # Outcomes = [o for o in iterArchiveFiles() if o.get('m_Name') == "Outcome"]
    # dumpDeep(Outcomes, "Outcomes.yaml")

if __name__ == "__main__":
    asyncio.run(main())
