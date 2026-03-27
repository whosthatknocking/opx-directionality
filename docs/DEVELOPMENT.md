# Development

## Local Environment

Create and activate a local environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

## Common Commands

Run the fetcher from the installed console script:

```bash
opx-directionality
```

Run the viewer from the installed console script:

```bash
opx-viewer --storage-kind file --storage-target output/runs --open
```

Run the fetcher directly from the repo without installing scripts:

```bash
PYTHONPATH=src python3 -m opx.fetcher
```

Run the viewer directly from the repo without installing scripts:

```bash
PYTHONPATH=src python3 -m opx.viewer --storage-kind file --storage-target output/runs --open
```

## Quality Checks

Run lint:

```bash
.venv/bin/python -m pylint $(find src tests -name '*.py' | sort)
```

Run unit tests:

```bash
.venv/bin/python -m pytest -q
```

## Notes

- Keep runtime/product behavior aligned with [PROJECT_SPEC.md](/Users/emt/Workspace/opx-directionality/docs/PROJECT_SPEC.md).
- Keep user-facing docs aligned across [README.md](/Users/emt/Workspace/opx-directionality/README.md), [USER_GUIDE.md](/Users/emt/Workspace/opx-directionality/docs/USER_GUIDE.md), and [VALIDATION.md](/Users/emt/Workspace/opx-directionality/docs/VALIDATION.md).
