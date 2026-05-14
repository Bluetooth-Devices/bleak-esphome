# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## What this library is

`bleak-esphome` is the **host-side** Bleak backend that lets a Python app drive
Bluetooth via an ESPHome Bluetooth Proxy node. It is _not_ the firmware — the
proxy firmware lives in the `esphome/esphome` repository under
`esphome/components/bluetooth_proxy/`. This package wires an
`aioesphomeapi.APIClient` to an `ESPHomeScanner` + `ESPHomeClient`, with no
Home Assistant dependency. See `docs/architecture.md` for the full picture.

## Layout

- `src/bleak_esphome/` — package source (importable as `bleak_esphome`).
- `src/bleak_esphome/backend/` — Bleak scanner/client glue (`scanner.py`,
  `client.py`, `device.py`, `cache.py`, `characteristic.py`, `descriptor.py`,
  `service.py`).
- `src/bleak_esphome/connect.py` — public `connect_scanner()` entry point and
  feature-flag negotiation via
  `DeviceInfo.bluetooth_proxy_feature_flags_compat(api_version)`.
- `tests/` — pytest suite (mirrors `src/` layout under `tests/backend/`).
- `docs/` — Sphinx documentation (`make -C docs html` to build locally).
- `examples/` — minimal runnable usage examples.

## Toolchain

- **Python**: `>=3.11, <3.15`. Do not use syntax or stdlib added after 3.11.
- **Package manager**: [Poetry](https://python-poetry.org). Install with
  `poetry install`. Dev dependencies include `pytest`, `pytest-asyncio`,
  `pytest-cov`, `pytest-codspeed`.
- **Build**: Poetry + a Cython build step (`build_ext.py`). Generated `*.c`
  files are excluded from the sdist.

## Style and formatting — non-negotiable

The pre-commit suite runs in CI and **will fail the build** if any hook fails.
Match these rules locally before pushing or your PR will be red.

- **Line length: 88 characters.** Both `ruff` (via `tool.ruff.line-length` in
  `pyproject.toml`) and `black` enforce this. This applies to **docstrings and
  comments too** — ruff's `E501` does not exempt them. Wrap long docstring
  summaries onto multiple lines rather than letting them spill past column 88.
- **Formatter**: `black` (the `black-pre-commit-mirror` hook). Run
  `poetry run black .` if you want to fix formatting in bulk.
- **Linter**: `ruff` with `select = [B, D, C4, S, F, E, W, UP, I, RUF]`.
  Tests are exempt from most `D` (docstring) rules and from `S101` (assert).
  See `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml` for the full set.
- **Type checking**: `mypy` in strict-ish mode (`disallow_untyped_defs`,
  `disallow_any_generics`, `warn_unreachable`, `warn_unused_ignores`). Tests
  are allowed untyped defs.
- **Modern syntax**: `pyupgrade --py311-plus` runs in pre-commit. Use 3.11+
  syntax (`X | None` over `Optional[X]`, PEP 604 unions, etc.).
- **Imports**: `ruff` handles `isort`. First-party packages are
  `bleak_esphome` and `tests`.
- **YAML / Markdown / JSON**: formatted by `prettier` with
  `--tab-width 2`.
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org)
  enforced by `commitizen` (commit-msg hook) and `commitlint` in CI. Use
  `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`, etc.
- **Misc hygiene hooks** (from `pre-commit/pre-commit-hooks`):
  `debug-statements`, `check-builtin-literals`, `check-case-conflict`,
  `check-docstring-first`, `check-json`, `check-toml`, `check-xml`,
  `check-yaml`, `detect-private-key`, `end-of-file-fixer`,
  `trailing-whitespace`.

The canonical command to validate everything locally is:

```shell
poetry run pre-commit run --all-files
```

Run it before pushing — CI runs the same set.

## Tests

- Run the full suite: `poetry run pytest`.
- A single file: `poetry run pytest tests/backend/test_device.py -v`.
- Coverage is collected automatically (`--cov=bleak_esphome`); the report is
  printed to the terminal.
- Tests are `pytest-asyncio` based — mark coroutine tests with
  `@pytest.mark.asyncio`.
- Mirror new source modules with a matching `tests/backend/test_<name>.py`.
- Cython is built in-place by Poetry; if imports fail with "module not
  compiled", re-run `poetry install`.

## Common pitfalls

- **Docstring overruns are the #1 CI failure.** Test functions with long
  descriptive docstrings often cross column 88. Either wrap the summary onto
  multiple lines or shorten it.
- **`asyncio.Future` race**: when scheduling a `call_later` callback that may
  `set_exception` on a future, always guard with `if not fut.done()`. Same
  shape appears in several `wait_for_*` helpers — keep an eye out.
- **Don't add Home Assistant imports.** This library is intentionally
  HA-free; `APIConnectionManager` + `ESPHomeDeviceConfig` is the standalone
  entry point.

## When in doubt

- Read `docs/architecture.md` for how the pieces connect.
- Read `CONTRIBUTING.md` for the human-oriented contribution flow.
- Read `pyproject.toml` — it is the source of truth for tool config.
