# iquip

Ion trap Quantum computing User Interface Project

[![Pylint](https://github.com/snu-quiqcl/iquip/actions/workflows/pylint.yml/badge.svg)](https://github.com/snu-quiqcl/iquip/actions/workflows/pylint.yml)
[![Unit test](https://github.com/snu-quiqcl/iquip/actions/workflows/unittest.yml/badge.svg)](https://github.com/snu-quiqcl/iquip/actions/workflows/unittest.yml)

## Starting iquip from this checkout

The repository includes `config_template.json`, but does not install an `iquip`
console script. Create a normal qiwis configuration and run the repository module
with its existing virtual environment:

```sh
cp config_template.json config.json
.venv/bin/python -m iquip -c ./config.json
```

This preserves qiwis's existing `-c/--config` and `-m/--maximize` options. The
configuration file remains the source for normal apps, constants, and initial
layout.

## Restoring Builder windows

Builder session persistence is opt-in. On the first run, choose a separate state
file (it need not exist yet):

```sh
.venv/bin/python -m iquip -c ./config.json \
  --builder-state-file ./state/builders.json
```

Use the same command on later runs to restore the saved Builders. Absolute paths
and `~` home-directory paths are accepted. Relative state paths are resolved from
the process's current working directory, not from the configuration file's
directory. Omitting `--builder-state-file` disables both restoration and saving
and retains the previous startup behavior.

Each open Builder record stores:

- a stable instance ID and the qiwis app/window name;
- experiment file path and class name;
- typed experiment arguments, including scan configurations;
- pipeline, priority, and optional scheduled date/time; and
- the center MDI window's position and size.

The UTF-8 file is human-readable JSON with schema
`"iquip.builder-session"` and version `1`. Values use JSON booleans, numbers,
strings, arrays, objects, and null; non-finite numbers are rejected. Live Qt
objects and executable serialization are never stored.

Changes are saved shortly after Builder creation, intentional closure, argument
or submission-setting edits, and window moves/resizes. A final snapshot is taken
as the main window begins to close, before qiwis tears down Builder frames. This
also commits a valid value still present in the focused spin-box editor. Writes
use a temporary file beside the state file and atomic replacement, so a failed
write leaves the preceding file intact. Parent directories are created when a
save is first needed.

At startup, experiment metadata is fetched through the normal proxy API and each
Builder is created through qiwis's normal app-registration path. Restoration only
opens and configures widgets; it never submits an experiment. Saved values are
checked against current metadata and widget validation. A removed argument,
enumeration choice, changed range/precision, unavailable experiment, or network
failure rejects that Builder while restoration continues for the remaining
records. A Builder already declared in the normal qiwis configuration is restored
into that existing instance instead of opening a duplicate window.

Autosaving is disabled until all asynchronous restore attempts finish. Quitting
during restoration leaves the input snapshot untouched and waits for outstanding
metadata threads to finish before Qt tears them down; a request already in progress
may therefore delay exit until its existing 10-second network timeout. A malformed,
unreadable, or unsupported-version file is also left untouched and automatic writes
are disabled for that run. If only some records fail, the original input is first
copied to a collision-safe file named like
`builders.json.recovery-YYYYMMDD-HHMMSS-...json`; only after that succeeds may the
working session file be replaced. If the recovery copy fails, writes remain
disabled. All such errors and backup paths are reported through the configured
Logger app.

Window geometry is restored only when it has useful dimensions and intersects
the current MDI workspace. Invalid or off-screen geometry falls back to qiwis's
normal placement without discarding otherwise valid Builder settings. This does
not persist the overall main-window or non-Builder dock layout.

### Manual verification checklist

1. Start with a nonexistent state path, open two Builders for the same experiment,
   give them different tags and values (including a scan), then move/resize both.
2. Type a valid number in a spin box without moving focus and quit normally.
3. Relaunch with the same command and confirm both independent Builders, values,
   scheduler settings, titles, and reasonable geometry return without any run
   being submitted.
4. Close one Builder intentionally, wait briefly, relaunch, and confirm only the
   remaining Builder returns.
5. With iquip stopped, corrupt a copy of one record and relaunch. Confirm the
   other records restore, Logger reports the failed identity, and a recovery file
   preserves the original input.
