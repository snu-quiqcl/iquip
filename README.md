# iquip

Ion trap Quantum computing User Interface Project

[![Pylint](https://github.com/snu-quiqcl/iquip/actions/workflows/pylint.yml/badge.svg)](https://github.com/snu-quiqcl/iquip/actions/workflows/pylint.yml)
[![Unit test](https://github.com/snu-quiqcl/iquip/actions/workflows/unittest.yml/badge.svg)](https://github.com/snu-quiqcl/iquip/actions/workflows/unittest.yml)

## Usage

```sh
cp config_template.json config.json
python -m iquip -c ./config.json
```

Builder-window persistence is opt-in:

```sh
python -m iquip -c ./config.json --builder-state-file ./state/builders.json
```

Use the same state path on later runs. Absolute paths and `~` are supported;
relative paths are resolved from the current working directory. Omitting the
option disables Builder persistence.

The version-1 UTF-8 JSON session stores each open Builder's experiment identity,
instance name, typed arguments (including scans), submission settings, and MDI
geometry. It autosaves after relevant changes and atomically saves once more on
normal shutdown. Restoration configures the UI only and never submits an
experiment.

Malformed or unsupported files are left untouched and disable writes for that
run. If individual records fail, the original is preserved as a collision-safe
`*.recovery-*.json` backup before autosaving resumes. Errors are shown in Logger.
Invalid or off-screen Builder geometry falls back to qiwis placement; the main
window and non-Builder dock layout are not persisted.
