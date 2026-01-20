# Ableton Git Setup

Version control for Ableton Live projects with human-readable diffs.

## What it does

- Tracks `.als` files in git with semantic diffs
- Generates `.als.txt` summaries showing tracks, devices, clips, and settings
- Auto-generates summaries on commit via pre-commit hook
- Shows meaningful changes instead of binary gibberish

## Setup

1. Copy `ableton_git_setup.py` into your Ableton project folder
2. Run it: `python ableton_git_setup.py`
3. Delete the setup script (it's in `.gitignore` anyway)

## Usage

### Daily workflow

```bash
# After working in Ableton and saving
git add *.als
git commit -m "Added verse section"

# The pre-commit hook automatically:
# - Generates/updates .als.txt summaries
# - Stages them with your commit
# - Shows what changed
```

### View changes before committing

```bash
# See what changed in terminal
git diff *.als

# Or regenerate summaries to view .txt files
python .git-filters/generate-summary.py --all
```

### Watch mode (auto-regenerate while working)

```bash
python .git-filters/generate-summary.py --watch
```

### Updating to latest version

Run the setup script again in an existing project - it detects the setup and only updates scripts.

## What gets tracked

- Project tempo, time signature, key, loop region
- Track names, colors, mixer settings (volume, pan, sends)
- Track routing, freeze status, groups
- Devices and their parameters
- Audio clips with file references, fades, warp settings
- MIDI clips with note count and pitch range
- Arrangement vs session clip separation
- Session clip launch settings and follow actions
- Markers, scenes, and more

## What's ignored

- `Backup/` folder
- `*.als.bak` files
- Audio files go to Git LFS (wav, mp3, aif, flac)

## Example diff

```diff
 Tempo: 120 BPM
-[1] Bass (Rose) [Vol: 0dB, Pan: C]
+[1] Bass (Rose) [Vol: +2.0dB, Pan: L25]
     Devices:
-      - Filter: Cutoff: 500Hz
+      - Filter: Cutoff: 2.5kHz
     Arrangement (1):
-      - "Bass" @ 1.1.0 - 32.1.0
+      - "Bass" @ 1.1.0 - 64.1.0
```

## Files created

```
your-project/
├── .git/
│   └── hooks/
│       └── pre-commit       # Auto-generates summaries on commit
├── .git-filters/
│   ├── als-textconv-semantic.py  # Converts .als to readable text
│   └── generate-summary.py       # Manual summary generation
├── .gitattributes           # Configures .als diff and LFS
├── .gitignore               # Ignores Backup/, etc.
└── *.als.txt                # Generated summaries (tracked)
```

## Requirements

- Python 3
- Git
- Git LFS (for audio files)

## License

MIT License - see [LICENSE](LICENSE) for details.
