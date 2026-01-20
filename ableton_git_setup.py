#!/usr/bin/env python3
"""
Ableton Git Setup - Copy this file into any Ableton project folder and run it.
Works for both new projects and updating existing ones.
Usage: python ableton_git_setup.py
"""
import os
import sys
import subprocess

# Get the directory where this script is located
PROJECT_DIR = os.getcwd()

# Check for .als files
als_files = [f for f in os.listdir(PROJECT_DIR) if f.endswith('.als')]
if not als_files:
    print("ERROR: No .als files found in this folder")
    sys.exit(1)

# Detect if this is an existing project
filters_dir = os.path.join(PROJECT_DIR, '.git-filters')
is_existing = os.path.exists(filters_dir)

if is_existing:
    print(f"Updating Ableton git workflow in: {PROJECT_DIR}")
    print("(Existing project detected - updating scripts only)\n")
else:
    print(f"Setting up Ableton git workflow in: {PROJECT_DIR}")
    print("(New project - full setup)\n")

# Initialize git if needed (new projects only)
if not os.path.exists(os.path.join(PROJECT_DIR, '.git')):
    print("Initializing git repository...")
    subprocess.run(['git', 'init'], cwd=PROJECT_DIR)

# Create .git-filters directory
os.makedirs(filters_dir, exist_ok=True)

# Create als-textconv-semantic.py
print("Writing .git-filters/als-textconv-semantic.py...")
semantic_py = r'''#!/usr/bin/env python3
"""Semantic Git textconv for Ableton .als files."""
import sys, gzip, xml.etree.ElementTree as ET, os, re, math

COLORS = {"0": "Gray", "1": "Rose", "2": "Red", "3": "Orange", "4": "Gold",
    "5": "Yellow", "6": "Lime", "7": "Green", "8": "Teal", "9": "Cyan",
    "10": "Sky", "11": "Blue", "12": "Indigo", "13": "Purple", "14": "Violet",
    "15": "Pink", "16": "Hot Pink", "17": "Flesh", "18": "Tan", "19": "Peach",
    "20": "Khaki", "21": "Light Green", "22": "Sea Foam", "23": "Light Blue",
    "24": "Lavender", "25": "Light Purple", "26": "White", "69": "Default"}

# Warp mode names (Phase 7)
WARP_MODES = {0: "Beats", 1: "Tones", 2: "Texture", 3: "Re-Pitch", 4: "Complex", 6: "Complex Pro"}

# MIDI note names for display (Phase 3)
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Note names with flats for key display
NOTE_NAMES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

# Launch modes for session clips
LAUNCH_MODES = {0: "trigger", 1: "gate", 2: "toggle", 3: "repeat"}

# Launch quantization values
LAUNCH_QUANT = {0: "none", 1: "8 bars", 2: "4 bars", 3: "2 bars", 4: "1 bar",
                5: "1/2", 6: "1/2T", 7: "1/4", 8: "1/4T", 9: "1/8", 10: "1/8T",
                11: "1/16", 12: "1/16T", 13: "1/32"}

# Follow action types
FOLLOW_ACTIONS = {0: "none", 1: "stop", 2: "again", 3: "prev", 4: "next", 5: "first", 6: "last", 7: "any", 8: "other"}

# Crossfader assignment
CROSSFADE_STATES = {0: None, 1: "A", 2: "B"}

# Parameters to skip (internal/unimportant)
SKIP_PARAMS = {'LomId', 'LomIdView', 'OverwriteProtectionNumber', 'LastSelectedTimeableIndex',
    'LastSelectedClipEnvelopeIndex', 'ModulationSourceCount', 'IsFolded', 'IsExpanded',
    'ShouldShowPresetName', 'Annotation', 'UserName', 'ParametersListWrapper', 'LastPresetRef',
    'LockedScripts', 'SendsListWrapper', 'Pointee', 'ViewStateSesstionTrackWidth',
    'SourceContext', 'BranchSelectorRange', 'IsAutoSelectEnabled', 'ChainSelector'}

# Max params to show on one line before switching to multi-line format
MAX_INLINE_PARAMS = 4

def get_attr(elem, path, default=""):
    if elem is None: return default
    node = elem.find(path)
    return node.get("Value", default) if node is not None else default

def get_preset_name(dev):
    for elem in dev.iter():
        if elem.tag == 'RelativePath':
            path = elem.get('Value', '')
            if path.endswith('.adv'): return os.path.splitext(os.path.basename(path))[0]
    return None

def get_macro_display_names(dev):
    """Extract MacroDisplayNames.X -> human readable name mapping from a device."""
    names = {}
    for child in dev:
        if child.tag.startswith('MacroDisplayNames.'):
            try:
                idx = int(child.tag.split('.')[1])
                name = child.get('Value', '')
                # Skip default names like "Macro 1", "Macro 2", etc.
                if name and not re.match(r'^Macro \d+$', name):
                    names[idx] = name
            except (ValueError, IndexError):
                pass
    return names

# Phase 1: Format volume as dB
def format_db(linear_value, default_linear=1.0):
    """Convert linear volume (0-2) to dB. Returns string like '0dB', '-6dB', '-inf'."""
    try:
        val = float(linear_value)
        if val <= 0:
            return "-inf"
        db = 20 * math.log10(val)
        if abs(db) < 0.1:
            return "0dB"
        return f"{db:+.1f}dB" if db != int(db) else f"{int(db):+d}dB"
    except:
        return "0dB"

# Phase 1: Format pan as L/C/R
def format_pan(pan_value):
    """Convert pan value (-1 to 1) to L50/C/R50 format."""
    try:
        val = float(pan_value)
        if abs(val) < 0.01:
            return "C"
        pct = int(abs(val) * 50)
        return f"L{pct}" if val < 0 else f"R{pct}"
    except:
        return "C"

# Phase 1: Parse mixer settings (volume, pan, solo, mute, sends)
def parse_track_mixer(track):
    """Parse mixer settings from a track."""
    mixer = track.find(".//DeviceChain/Mixer")
    if mixer is None:
        return {}

    volume = get_attr(mixer, "Volume/Manual", "1")
    pan = get_attr(mixer, "Pan/Manual", "0")
    solo = get_attr(mixer, "SoloSink", "false") == "true"
    # Speaker: true = on (not muted), false = muted
    muted = get_attr(mixer, "Speaker/Manual", "true") == "false"

    # Parse sends
    sends = []
    sends_elem = mixer.find("Sends")
    if sends_elem is not None:
        for holder in sends_elem.findall("TrackSendHolder"):
            send_val = get_attr(holder, "Send/Manual", "0.0003162277571")  # -inf default
            sends.append(format_db(send_val))

    return {
        "volume": format_db(volume),
        "pan": format_pan(pan),
        "solo": solo,
        "muted": muted,
        "sends": sends
    }

# Phase 3: Convert MIDI pitch to note name
def midi_note_name(pitch):
    """Convert MIDI pitch number to note name like C3, F#4."""
    try:
        pitch = int(pitch)
        octave = (pitch // 12) - 2  # MIDI octave convention
        note = NOTE_NAMES[pitch % 12]
        return f"{note}{octave}"
    except:
        return str(pitch)

# Phase 3: Parse MIDI notes from a clip
def parse_midi_notes(clip):
    """Parse MIDI notes and return summary (count, pitch range)."""
    pitches = []
    note_count = 0

    # Ableton stores notes in KeyTracks - each KeyTrack has a MidiKey (pitch)
    # and contains MidiNoteEvents (timing/duration) for that pitch
    keytracks = clip.findall(".//Notes/KeyTracks/KeyTrack")
    for kt in keytracks:
        midi_key = kt.find("MidiKey")
        if midi_key is not None:
            try:
                pitch = int(midi_key.get("Value", 0))
                notes_in_track = kt.findall("Notes/MidiNoteEvent")
                if notes_in_track:
                    pitches.append(pitch)
                    note_count += len(notes_in_track)
            except:
                pass

    if not pitches or note_count == 0:
        return None

    return {
        "count": note_count,
        "range": f"{midi_note_name(min(pitches))}-{midi_note_name(max(pitches))}"
    }

# Phase 2: Get audio file reference
def get_audio_ref(clip):
    """Get the audio file name from an audio clip."""
    # Try RelativePath first
    ref = clip.find(".//SampleRef/FileRef/RelativePath")
    if ref is not None:
        path = ref.get("Value", "")
        if path:
            return os.path.basename(path)
    # Try Name as fallback
    ref = clip.find(".//SampleRef/FileRef/Name")
    if ref is not None:
        return ref.get("Value", "")
    return None

# Phase 4: Get clip gain/transpose adjustments
def get_clip_adjustments(clip):
    """Get volume, transpose, and fine tune adjustments for a clip."""
    adjustments = []

    # Volume (SampleVolume for audio clips)
    volume = get_attr(clip, "SampleVolume", "1")
    try:
        vol = float(volume)
        if abs(vol - 1.0) > 0.01:  # Not default
            adjustments.append(format_db(vol))
    except:
        pass

    # Transpose (semitones)
    transpose = get_attr(clip, "PitchCoarse", "0")
    try:
        t = int(float(transpose))
        if t != 0:
            adjustments.append(f"{t:+d}st")
    except:
        pass

    # Fine tune (cents)
    fine = get_attr(clip, "PitchFine", "0")
    try:
        f = float(fine)
        if abs(f) > 0.1:
            adjustments.append(f"{f:+.0f}ct")
    except:
        pass

    return adjustments

# Phase 6: Get fade info
def get_fades(clip):
    """Get fade in/out info for audio clip."""
    fades = []

    # Check if fades are enabled
    fades_on = get_attr(clip, "Fades/IsDefaultFadeIn", "true") == "false" or \
               get_attr(clip, "Fades/IsDefaultFadeOut", "true") == "false"

    fade_in = get_attr(clip, "Fades/FadeInLength", "0")
    fade_out = get_attr(clip, "Fades/FadeOutLength", "0")

    try:
        fi = float(fade_in)
        if fi > 0.001:
            fades.append(f"fade in: {fi:.2f}s" if fi >= 1 else f"fade in: {fi*1000:.0f}ms")
    except:
        pass

    try:
        fo = float(fade_out)
        if fo > 0.001:
            fades.append(f"fade out: {fo:.2f}s" if fo >= 1 else f"fade out: {fo*1000:.0f}ms")
    except:
        pass

    return fades

# Phase 7: Get warp info
def get_warp_info(clip):
    """Get warp mode and marker count for audio clip."""
    is_warped = get_attr(clip, "IsWarped", "true") == "true"
    if not is_warped:
        return None

    warp_mode = get_attr(clip, "WarpMode", "0")
    mode_name = WARP_MODES.get(int(warp_mode), "Unknown")

    markers = clip.findall(".//WarpMarkers/WarpMarker")
    marker_count = len(markers) if markers else 0

    # Only report if there are custom markers beyond the default 2
    if marker_count > 2:
        return {"mode": mode_name, "markers": marker_count}
    elif marker_count > 0:
        return {"mode": mode_name}
    return None

# Phase 10: Check for groove
def has_groove(clip):
    """Check if clip has a groove applied."""
    groove_id = get_attr(clip, "GrooveSettings/GrooveId", "-1")
    try:
        return int(groove_id) >= 0
    except:
        return False

# Extended: Parse project-level info (key, loop)
def parse_project_info(root):
    """Parse project key/scale and loop region."""
    info = {}

    # Key/Scale
    scale = root.find('.//ScaleInformation')
    if scale is not None:
        try:
            root_note = int(get_attr(scale, 'RootNote', '0'))
            scale_name = get_attr(scale, 'Name', 'Major')
            if 0 <= root_note < 12:
                info['key'] = f"{NOTE_NAMES_FLAT[root_note]} {scale_name}"
        except:
            pass

    # Loop region
    transport = root.find('.//Transport')
    if transport is not None and get_attr(transport, 'LoopOn', 'false') == 'true':
        try:
            start = float(get_attr(transport, 'LoopStart', '0'))
            length = float(get_attr(transport, 'LoopLength', '16'))
            info['loop'] = {
                'start_bar': int(start // 4) + 1,
                'end_bar': int((start + length) // 4) + 1,
                'bars': int(length // 4)
            }
        except:
            pass

    return info

# Extended: Parse track routing
def parse_track_routing(track):
    """Parse input/output routing for a track."""
    routing = {}

    for rtype, key in [('AudioInputRouting', 'input'), ('AudioOutputRouting', 'output'),
                       ('MidiInputRouting', 'midi_in'), ('MidiOutputRouting', 'midi_out')]:
        elem = track.find(f'.//DeviceChain/{rtype}')
        if elem is not None:
            upper = get_attr(elem, 'UpperDisplayString', '')
            lower = get_attr(elem, 'LowerDisplayString', '')
            if upper:
                routing[key] = f"{upper} {lower}".strip() if lower else upper

    return routing

# Extended: Parse track state (freeze, group, delay, crossfader)
def parse_track_state(track):
    """Parse additional track state properties."""
    state = {}

    # Freeze status
    if get_attr(track, 'Freeze', 'false') == 'true':
        state['frozen'] = True

    # Track group ID
    group_id = get_attr(track, 'TrackGroupId', '-1')
    if group_id != '-1':
        state['group_id'] = group_id

    # Track delay
    delay_elem = track.find('TrackDelay')
    if delay_elem is not None:
        delay_val = get_attr(delay_elem, 'Value', '0')
        try:
            delay_ms = float(delay_val)
            if abs(delay_ms) > 0.01:
                state['delay_ms'] = delay_ms
        except:
            pass

    # Crossfader assignment
    crossfade = get_attr(track, './/Mixer/CrossFadeState', '0')
    try:
        cf_state = CROSSFADE_STATES.get(int(crossfade))
        if cf_state:
            state['crossfade'] = cf_state
    except:
        pass

    return state

# Extended: Build group track mapping
def build_group_map(root):
    """Build a mapping from group track IDs to their names."""
    groups = {}
    for track in root.findall('.//Tracks/GroupTrack'):
        track_id = track.get('Id')
        name = get_attr(track, 'Name/EffectiveName', 'Group')
        if track_id:
            groups[track_id] = name
    return groups

# Extended: Parse session clip launch settings
def parse_launch_settings(clip):
    """Parse launch mode, quantization, and follow actions for session clips."""
    settings = {}

    # Launch mode (only if not default trigger)
    launch_mode = get_attr(clip, 'LaunchMode', '0')
    try:
        mode = int(launch_mode)
        if mode != 0:  # Not trigger (default)
            settings['launch_mode'] = LAUNCH_MODES.get(mode, str(mode))
    except:
        pass

    # Launch quantization (only if not global)
    launch_quant = get_attr(clip, 'LaunchQuantisation', '0')
    try:
        quant = int(launch_quant)
        if quant > 0:  # 0 = global/none
            settings['launch_quant'] = LAUNCH_QUANT.get(quant, str(quant))
    except:
        pass

    # Follow action
    fa_enabled = get_attr(clip, 'FollowAction/FollowActionEnabled', 'false')
    if fa_enabled == 'true':
        fa_a = get_attr(clip, 'FollowAction/FollowActionA', '0')
        fa_time = get_attr(clip, 'FollowAction/FollowTime', '4')
        try:
            action = FOLLOW_ACTIONS.get(int(fa_a), 'unknown')
            if action != 'none':
                time_bars = float(fa_time) / 4
                settings['follow'] = f"{action} @ {time_bars:.0f} bar" if time_bars == 1 else f"{action} @ {time_bars:.0f} bars"
        except:
            pass

    # RAM mode
    if get_attr(clip, 'Ram', 'false') == 'true':
        settings['ram'] = True

    # HiQ mode (only for audio, default is true so only show if false)
    # Actually, we want to show if it's explicitly set differently from normal

    return settings

def format_param(value, name=""):
    try:
        fval = float(value)
        name_lower = name.lower()
        if fval == 0 or fval == 1:
            if ('time' not in name_lower and 'rate' not in name_lower and
                ('on' in name_lower or 'sync' in name_lower or 'link' in name_lower or 'freeze' in name_lower)):
                return 'on' if fval == 1 else 'off'
        if 0 <= fval <= 1 and ('wet' in name_lower or 'mix' in name_lower or 'amount' in name_lower
            or 'feedback' in name_lower or 'depth' in name_lower or 'gain' in name_lower
            or 'drive' in name_lower or 'resonance' in name_lower): return f"{fval * 100:.0f}%"
        elif 'freq' in name_lower and 'mod' not in name_lower: return f"{fval/1000:.1f}kHz" if fval >= 1000 else f"{fval:.0f}Hz"
        elif ('timesec' in name_lower or 'attack' in name_lower or 'release' in name_lower or 'predelay' in name_lower) and fval < 10:
            return f"{fval*1000:.0f}ms" if fval < 1 else f"{fval:.2f}s"
        elif fval == int(fval): return str(int(fval))
        else: return f"{fval:.2f}"
    except: return str(value)

def format_beats(beat_str):
    try:
        beats = float(beat_str)
        return f"{int(beats // 4) + 1}.{(beats % 4) + 1:.1f}"
    except: return beat_str

def parse_track(track, is_master=False):
    name = get_attr(track, "Name/EffectiveName", "Untitled")
    color = COLORS.get(get_attr(track, "Color", "69"), "Default")

    # Phase 1: Get mixer settings
    mixer = parse_track_mixer(track)

    # Extended: Get routing and state (not for master)
    routing = {} if is_master else parse_track_routing(track)
    state = {} if is_master else parse_track_state(track)

    devices = []
    # Master track has different device path
    if is_master:
        devices_elem = track.find(".//DeviceChain/Devices")
    else:
        devices_elem = track.find(".//DeviceChain/DeviceChain/Devices")
    if devices_elem is not None:
        for dev in devices_elem:
            if dev.tag in ("AudioEffectBranchGroup", "MidiEffectBranchGroup", "InstrumentBranchGroup"): continue
            preset = get_preset_name(dev) or get_attr(dev, "UserName") or dev.tag
            is_on = get_attr(dev, "On/Manual", "true") == "true"

            # Get macro display names for GroupDevice types (Instrument/Audio/Midi Racks)
            macro_names = {}
            if dev.tag.endswith('GroupDevice'):
                macro_names = get_macro_display_names(dev)

            params = {}
            for child in dev:
                if child.tag in SKIP_PARAMS or child.tag == 'On': continue
                if child.tag.startswith('MacroDisplayNames.'): continue  # Skip display name elements

                # Handle MacroControls.X - use display name if available
                if child.tag.startswith('MacroControls.'):
                    manual = child.find('Manual')
                    if manual is not None and manual.get('Value'):
                        try:
                            idx = int(child.tag.split('.')[1])
                            # Use custom display name if available, otherwise skip default macros
                            if idx in macro_names:
                                param_name = macro_names[idx]
                                params[param_name] = format_param(manual.get('Value'), param_name)
                        except (ValueError, IndexError):
                            pass
                    continue

                manual = child.find('Manual')
                if manual is not None and manual.get('Value'):
                    params[child.tag] = format_param(manual.get('Value'), child.tag)
            devices.append({"name": preset, "is_on": is_on, "params": params})

    # Parse clips - separate arrangement clips (on timeline) from session clips (in slots)
    def parse_clip(clip):
        is_audio = clip.tag == "AudioClip"
        clip_name = get_attr(clip, "Name", "unnamed")
        start = format_beats(clip.get("Time", "0"))
        end = format_beats(get_attr(clip, "CurrentEnd", "?"))
        looped = get_attr(clip, "Loop/LoopOn", "false") == "true"
        muted = get_attr(clip, "Disabled", "false") == "true"
        loop_start = get_attr(clip, "Loop/LoopStart", "0")
        start_rel = get_attr(clip, "Loop/StartRelative", "0")
        clip_info = {"name": clip_name, "start": start, "end": end, "looped": looped, "muted": muted,
                     "time_float": float(clip.get("Time", "0"))}
        try:
            ls, sr = float(loop_start), float(start_rel)
            if sr != 0 or ls != 0:
                clip_info["clip_offset"] = format_beats(str(ls + sr))
        except: pass
        if is_audio:
            audio_ref = get_audio_ref(clip)
            if audio_ref:
                clip_info["audio_file"] = audio_ref
            adjustments = get_clip_adjustments(clip)
            if adjustments:
                clip_info["adjustments"] = adjustments
            fades = get_fades(clip)
            if fades:
                clip_info["fades"] = fades
            warp = get_warp_info(clip)
            if warp:
                clip_info["warp"] = warp
        else:
            midi_info = parse_midi_notes(clip)
            if midi_info:
                clip_info["midi_notes"] = midi_info
        if has_groove(clip):
            clip_info["groove"] = True
        return clip_info

    # Arrangement clips - clips placed on the timeline (under ArrangerAutomation/Events)
    arrangement_clips = []
    for clip in track.findall(".//ArrangerAutomation/Events/AudioClip") + \
                track.findall(".//ArrangerAutomation/Events/MidiClip"):
        arrangement_clips.append(parse_clip(clip))
    arrangement_clips.sort(key=lambda c: c["time_float"])

    # Session clips - clips in clip slots (under ClipSlotList)
    session_clips = []
    for clip in track.findall(".//ClipSlotList//AudioClip") + \
                track.findall(".//ClipSlotList//MidiClip"):
        clip_info = parse_clip(clip)
        # Add launch settings for session clips
        launch = parse_launch_settings(clip)
        if launch:
            clip_info["launch"] = launch
        session_clips.append(clip_info)

    return {"type": track.tag.replace("Track", ""), "name": name, "color": color,
            "devices": devices, "arrangement_clips": arrangement_clips,
            "session_clips": session_clips, "mixer": mixer,
            "routing": routing, "state": state}

# Phase 5: Parse master track
def parse_master_track(root):
    """Parse the master track."""
    master = root.find(".//MasterTrack")
    if master is None:
        return None
    return parse_track(master, is_master=True)

# Phase 8: Parse scenes
def parse_scenes(root):
    """Parse scene names."""
    scenes = []
    scenes_elem = root.find(".//Scenes")
    if scenes_elem is not None:
        for i, scene in enumerate(scenes_elem.findall("Scene"), 1):
            name = get_attr(scene, "Name", "")
            # Only include named scenes (not default empty names)
            if name and not name.startswith("Scene "):
                scenes.append({"index": i, "name": name})
    return scenes

# Phase 9: Check for tempo automation
def is_tempo_automated(root):
    """Check if tempo has automation."""
    # Look for automation on tempo
    tempo_automation = root.find(".//MasterTrack//AutomationEnvelopes//Envelopes//AutomationEnvelope")
    if tempo_automation is not None:
        # Check if it's linked to tempo
        pointee = tempo_automation.find(".//PointeeId")
        if pointee is not None:
            return True

    # Alternative: check for tempo events in the automation
    tempo_events = root.findall(".//MasterTrack//AutomationEnvelopes//Envelopes//AutomationEnvelope//Events//FloatEvent")
    return len(tempo_events) > 1

def parse_als(filepath):
    try:
        with open(filepath, 'rb') as f: xml_data = gzip.decompress(f.read()).decode('utf-8')
    except Exception as e: return {"error": str(e)}
    root = ET.fromstring(xml_data)

    # Extended: Project-level info (key, loop)
    project_info = parse_project_info(root)

    # Extended: Build group track mapping for resolving group names
    group_map = build_group_map(root)

    tracks = {"audio": [], "midi": [], "return": [], "group": []}
    tracks_elem = root.find(".//Tracks")
    if tracks_elem is not None:
        for t in tracks_elem:
            info = parse_track(t)
            # Resolve group ID to group name
            if info.get('state', {}).get('group_id') and info['state']['group_id'] in group_map:
                info['state']['group_name'] = group_map[info['state']['group_id']]
            if t.tag == "AudioTrack": tracks["audio"].append(info)
            elif t.tag == "MidiTrack": tracks["midi"].append(info)
            elif t.tag == "ReturnTrack": tracks["return"].append(info)
            elif t.tag == "GroupTrack": tracks["group"].append(info)

    # Locators/markers
    locators = []
    for loc in root.findall(".//Locators/Locators/Locator"):
        loc_name = get_attr(loc, "Name", "")
        loc_time = get_attr(loc, "Time", "0")
        if loc_name:
            locators.append({"name": loc_name, "time": format_beats(loc_time)})

    # Phase 5: Master track
    master = parse_master_track(root)

    # Phase 8: Scenes
    scenes = parse_scenes(root)

    # Phase 9: Tempo automation
    tempo_automated = is_tempo_automated(root)

    return {"creator": root.get("Creator", "Unknown"), "tempo": get_attr(root, ".//Tempo/Manual", "120"),
            "time_sig": f"{get_attr(root, './/TimeSignature/Manual/Numerator', '4')}/{get_attr(root, './/TimeSignature/Manual/Denominator', '4')}",
            "tracks": tracks, "locators": locators, "master": master, "scenes": scenes,
            "tempo_automated": tempo_automated, "project_info": project_info}

def format_device_params(params, indent=""):
    """Format device parameters, using multi-line for many params."""
    if not params:
        return ""
    if len(params) <= MAX_INLINE_PARAMS:
        return f" ({', '.join(f'{k}={v}' for k,v in params.items())})"
    # Multi-line format for many parameters
    lines = [":"]
    for k, v in params.items():
        lines.append(f"{indent}    {k}: {v}")
    return "\n".join(lines)

# Phase 1: Format mixer info for track header
def format_mixer_info(mixer):
    """Format mixer settings for display in track header."""
    if not mixer:
        return ""

    parts = []

    # Solo/Mute flags first
    if mixer.get("solo"):
        parts.append("SOLO")
    if mixer.get("muted"):
        parts.append("MUTED")

    # Volume and pan
    vol = mixer.get("volume", "0dB")
    pan = mixer.get("pan", "C")
    parts.append(f"Vol: {vol}")
    parts.append(f"Pan: {pan}")

    # Sends (labeled A, B, C, etc.)
    sends = mixer.get("sends", [])
    for i, send in enumerate(sends):
        if send != "-inf":  # Only show non-silent sends
            label = chr(65 + i)  # A, B, C...
            parts.append(f"Send {label}: {send}")

    return f" [{', '.join(parts)}]" if parts else ""

def format_output(p):
    if "error" in p: return f"ERROR: {p['error']}"

    # Phase 9: Add [automated] flag to tempo if applicable
    tempo_str = f"{p['tempo']} BPM"
    if p.get('tempo_automated'):
        tempo_str += " [automated]"

    lines = ["=" * 60, "ABLETON PROJECT SUMMARY", "=" * 60, f"Creator: {p['creator']}"]

    # Extended: Project key
    proj = p.get('project_info', {})
    if proj.get('key'):
        lines.append(f"Key: {proj['key']}")

    lines.append(f"Tempo: {tempo_str}")
    lines.append(f"Time Signature: {p['time_sig']}")

    # Extended: Loop region
    if proj.get('loop'):
        loop = proj['loop']
        bar_word = "bar" if loop['bars'] == 1 else "bars"
        lines.append(f"Loop: bars {loop['start_bar']}-{loop['end_bar']} ({loop['bars']} {bar_word})")

    lines.append("")

    # Locators/markers
    if p.get('locators'):
        lines.extend(["-" * 40, "MARKERS:"])
        for loc in p['locators']:
            lines.append(f"  [{loc['time']}] {loc['name']}")
        lines.append("")

    for ttype, label in [("audio", "AUDIO"), ("midi", "MIDI"), ("return", "RETURN"), ("group", "GROUP")]:
        if p['tracks'][ttype]:
            lines.extend(["-" * 40, f"{label} TRACKS ({len(p['tracks'][ttype])}):"])
            for i, t in enumerate(p['tracks'][ttype], 1):
                # Build track header with state flags
                state = t.get('state', {})
                routing = t.get('routing', {})

                # State flags (frozen, crossfade)
                state_flags = []
                if state.get('frozen'):
                    state_flags.append("FROZEN")

                # Mixer info
                mixer_str = format_mixer_info(t.get('mixer', {}))

                # Build extra info (group, delay, crossfade)
                extra = []
                if state.get('crossfade'):
                    extra.append(f"XF: {state['crossfade']}")
                if state.get('delay_ms'):
                    extra.append(f"delay: {state['delay_ms']:.0f}ms")

                # Routing info (only show non-default)
                routing_str = ""
                input_r = routing.get('input', '')
                output_r = routing.get('output', '')
                # Show input only if not default "Ext. In"
                if input_r and not input_r.startswith('Ext. In'):
                    routing_str += f" In: {input_r}"
                # Show output only if not default "Master"
                if output_r and output_r != 'Master':
                    routing_str += f" → {output_r}"

                # Group membership
                group_str = ""
                if state.get('group_name'):
                    group_str = f" (in \"{state['group_name']}\")"

                # Build the header line
                flags_str = f" [{', '.join(state_flags)}]" if state_flags else ""
                extra_str = f" [{', '.join(extra)}]" if extra else ""
                lines.append(f"  [{i}] {t['name']} ({t['color']}){flags_str}{mixer_str}{extra_str}{routing_str}{group_str}")
                if t['devices']:
                    lines.append("      Devices:")
                    for d in t['devices']:
                        status = "" if d['is_on'] else "[OFF] "
                        param_str = format_device_params(d['params'], "          ")
                        lines.append(f"        - {status}{d['name']}{param_str}")
                # Helper to format a single clip
                def format_clip(c, is_session=False):
                    flags = []
                    if c.get('looped'): flags.append("loop")
                    if c.get('muted'): flags.append("muted")
                    if c.get('clip_offset'): flags.append(f"from {c['clip_offset']}")
                    if c.get('audio_file'): flags.append(c['audio_file'])
                    if c.get('midi_notes'):
                        mi = c['midi_notes']
                        flags.append(f"{mi['count']} notes, {mi['range']}")
                    if c.get('adjustments'): flags.extend(c['adjustments'])
                    if c.get('fades'): flags.extend(c['fades'])
                    if c.get('warp'):
                        w = c['warp']
                        warp_str = f"warped: {w['mode']}"
                        if 'markers' in w:
                            warp_str += f", {w['markers']} markers"
                        flags.append(warp_str)
                    if c.get('groove'): flags.append("groove")
                    # Session clip launch settings
                    if is_session and c.get('launch'):
                        launch = c['launch']
                        if launch.get('launch_mode'): flags.append(launch['launch_mode'])
                        if launch.get('launch_quant'): flags.append(launch['launch_quant'])
                        if launch.get('follow'): flags.append(f"follow: {launch['follow']}")
                        if launch.get('ram'): flags.append("RAM")
                    flag_str = f" [{', '.join(flags)}]" if flags else ""
                    return f"\"{c['name']}\" @ {c['start']} - {c['end']}{flag_str}"

                # Arrangement clips (on timeline) - show ALL of these
                arr_clips = t.get('arrangement_clips', [])
                sess_clips = t.get('session_clips', [])
                if arr_clips:
                    lines.append(f"      Arrangement ({len(arr_clips)}):")
                    for c in arr_clips:
                        lines.append(f"        - {format_clip(c)}")
                # Session clips (in slots) - show count and first few
                if sess_clips:
                    lines.append(f"      Session Slots ({len(sess_clips)}):")
                    for c in sess_clips[:3]:
                        lines.append(f"        - {format_clip(c, is_session=True)}")
                    if len(sess_clips) > 3:
                        lines.append(f"        ... and {len(sess_clips) - 3} more in slots")
            lines.append("")

    # Phase 5: Master track
    if p.get('master'):
        m = p['master']
        lines.extend(["-" * 40, "MASTER:"])
        mixer = m.get('mixer', {})
        if mixer:
            lines.append(f"  Volume: {mixer.get('volume', '0dB')}")
        if m.get('devices'):
            lines.append("  Devices:")
            for d in m['devices']:
                status = "" if d['is_on'] else "[OFF] "
                param_str = format_device_params(d['params'], "      ")
                lines.append(f"    - {status}{d['name']}{param_str}")
        lines.append("")

    # Phase 8: Scenes
    if p.get('scenes'):
        lines.extend(["-" * 40, "SCENES:"])
        for s in p['scenes']:
            lines.append(f"  [{s['index']}] {s['name']}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: als-textconv-semantic.py <filename>", file=sys.stderr); sys.exit(1)
    print(format_output(parse_als(sys.argv[1])))
'''

with open(os.path.join(filters_dir, 'als-textconv-semantic.py'), 'w', encoding='utf-8') as f:
    f.write(semantic_py)

# Create generate-summary.py
print("Writing .git-filters/generate-summary.py...")
generate_py = r'''#!/usr/bin/env python3
import sys, os, argparse, time
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location("semantic", os.path.join(script_dir, "als-textconv-semantic.py"))
semantic = module_from_spec(spec)
spec.loader.exec_module(semantic)

def generate_summary(als_path, output_path=None):
    if not os.path.exists(als_path): print(f"Error: File not found: {als_path}", file=sys.stderr); return False
    if output_path is None: output_path = als_path + ".txt"
    try:
        project = semantic.parse_als(als_path)
        with open(output_path, 'w', encoding='utf-8') as f: f.write(semantic.format_output(project))
        print(f"Generated: {output_path}")
        return True
    except Exception as e: print(f"Error processing {als_path}: {e}", file=sys.stderr); return False

def find_als_files(directory="."):
    return [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.als') and os.path.isfile(os.path.join(directory, f))]

def generate_all(directory="."):
    als_files = find_als_files(directory)
    if not als_files: print("No .als files found."); return
    print(f"Found {len(als_files)} .als file(s)")
    success = sum(1 for f in als_files if generate_summary(f))
    print(f"\nGenerated {success}/{len(als_files)} summaries")

def watch(directory=".", interval=5):
    print(f"Watching for .als changes in {os.path.abspath(directory)}\nPress Ctrl+C to stop\n")
    mtimes = {}
    try:
        while True:
            for als_path in find_als_files(directory):
                try:
                    mtime = os.path.getmtime(als_path)
                    if als_path not in mtimes or mtimes[als_path] < mtime:
                        if als_path in mtimes: print(f"\nDetected change: {als_path}")
                        generate_summary(als_path)
                        mtimes[als_path] = mtime
                except OSError: pass
            time.sleep(interval)
    except KeyboardInterrupt: print("\nStopped watching.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", help="Path to .als file")
    parser.add_argument("--all", "-a", action="store_true")
    parser.add_argument("--watch", "-w", action="store_true")
    args = parser.parse_args()
    if args.watch: watch()
    elif args.all: generate_all()
    elif args.file: generate_summary(args.file)
    else: parser.print_help()
'''

with open(os.path.join(filters_dir, 'generate-summary.py'), 'w', encoding='utf-8') as f:
    f.write(generate_py)

# Create pre-commit hook (always update to latest version)
print("Writing .git/hooks/pre-commit...")
hooks_dir = os.path.join(PROJECT_DIR, '.git', 'hooks')
os.makedirs(hooks_dir, exist_ok=True)

pre_commit = r'''#!/bin/sh
# Pre-commit hook for Ableton .als files - Windows compatible
REPO_ROOT=$(git rev-parse --show-toplevel)
GENERATED_ANY=0

# Use repo-relative temp dir for Windows compatibility
TEMP_DIR="$REPO_ROOT/.git/tmp"
mkdir -p "$TEMP_DIR"

generate_and_stage() {
    als_file="$1"
    full_path="$REPO_ROOT/$als_file"
    summary_file="${als_file}.txt"
    summary_path="$REPO_ROOT/$summary_file"
    if [ -f "$full_path" ]; then
        # Save old summary to temp file
        git show HEAD:"$summary_file" 2>/dev/null > "$TEMP_DIR/old_summary.txt" || echo "" > "$TEMP_DIR/old_summary.txt"

        # Generate new summary
        python "$REPO_ROOT/.git-filters/generate-summary.py" "$full_path"

        if [ -f "$summary_path" ]; then
            # Compare and show diff if changed
            if [ -s "$TEMP_DIR/old_summary.txt" ]; then
                if ! diff -q "$TEMP_DIR/old_summary.txt" "$summary_path" > /dev/null 2>&1; then
                    echo ""
                    echo "====== CHANGES IN: $als_file ======"
                    diff -u "$TEMP_DIR/old_summary.txt" "$summary_path" | tail -n +3 || true
                    echo "===================================="
                fi
            fi
            git add "$summary_path"
            GENERATED_ANY=1
        fi
    fi
}

STAGED_ALS=$(git diff --cached --name-only --diff-filter=ACM | grep '\.als$' || true)
if [ -n "$STAGED_ALS" ]; then
    echo "Generating summaries for staged .als files..."
    for als_file in $STAGED_ALS; do generate_and_stage "$als_file"; done
fi

echo "Checking for missing/outdated summaries..."
TRACKED_ALS=$(git ls-files '*.als' 2>/dev/null || true)
for als_file in $TRACKED_ALS; do
    full_path="$REPO_ROOT/$als_file"
    summary_path="$REPO_ROOT/${als_file}.txt"
    echo "$STAGED_ALS" | grep -q "^${als_file}$" && continue
    if [ ! -f "$summary_path" ]; then
        echo "  Missing summary for: $als_file"
        generate_and_stage "$als_file"
    elif [ "$full_path" -nt "$summary_path" ]; then
        echo "  Outdated summary for: $als_file"
        generate_and_stage "$als_file"
    fi
done

# Cleanup temp files
rm -f "$TEMP_DIR/old_summary.txt" 2>/dev/null

[ "$GENERATED_ANY" = "1" ] && echo "Summary generation complete." || echo "All summaries up to date."
exit 0
'''

with open(os.path.join(hooks_dir, 'pre-commit'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(pre_commit)

# For new projects only: create .gitattributes and .gitignore
if not is_existing:
    print("Creating .gitattributes...")
    gitattributes = '''*.als filter=als diff=als
*.wav filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.aif filter=lfs diff=lfs merge=lfs -text
*.flac filter=lfs diff=lfs merge=lfs -text
'''
    with open(os.path.join(PROJECT_DIR, '.gitattributes'), 'w', encoding='utf-8') as f:
        f.write(gitattributes)

    print("Creating .gitignore...")
    gitignore = '''Backup/
*.als.bak
__pycache__/
ableton_git_setup.py
'''
    with open(os.path.join(PROJECT_DIR, '.gitignore'), 'w', encoding='utf-8') as f:
        f.write(gitignore)

    # Configure git
    print("Configuring git...")
    subprocess.run(['git', 'config', 'filter.als.clean', 'cat'], cwd=PROJECT_DIR)
    subprocess.run(['git', 'config', 'filter.als.smudge', 'cat'], cwd=PROJECT_DIR)
    subprocess.run(['git', 'config', 'diff.als.textconv', 'python .git-filters/als-textconv-semantic.py'], cwd=PROJECT_DIR)

# Generate/regenerate summaries
print("\nGenerating summaries for .als files...")
subprocess.run([sys.executable, os.path.join(filters_dir, 'generate-summary.py'), '--all'], cwd=PROJECT_DIR)

if is_existing:
    print("""
========================================
Update complete!
========================================
Scripts have been updated to the latest version.
Summary files have been regenerated.

You can delete ableton_git_setup.py from this folder now.
========================================
""")
else:
    print("""
========================================
Setup complete!
========================================
Workflow:
  1. Work in Ableton, save
  2. git add *.als
  3. git commit -m "message"
  The diff will show what changed.

You can delete ableton_git_setup.py from this folder now.
========================================
""")

input("Press Enter to close...")
