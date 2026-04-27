# How to Deploy

Three deployment surfaces, in order of complexity:

1. [Local CLI](#local-cli) — single-user terminal workflow.
2. [Local engine + Docker / Compose](#local-engine--docker) — containerised CLI runs, useful for batch jobs or sharing a configured environment.
3. [Desktop installer (Windows MSI)](#desktop-installer-windows) — Tauri-bundled GUI app with the Python sidecar embedded; the user's machine doesn't need `uv` or Python.

The CLI and the engine each work standalone. The desktop installer bundles both behind a Tauri shell. Pick the surface that fits your distribution model.

For end-user workflows on a deployed install, see [How to Use](usage.md). For the code architecture, see [Architecture](../architecture.md).

---

## Local CLI

The simplest deployment — run directly on your machine.

```bash
# Install
uv sync --dev

# Configure
cp .env.example .env
# Edit .env with your LLM API key

# Run a single tailoring job
uv run python -m resume_operator run \
  --master data/master_resume.yaml \
  --job job.txt
```

Output files are written to `data/applications/{date}_{slug}/` by default. See [How to Use](usage.md#cli-walkthrough) for the full command surface.

---

## Local engine + Docker

### Build the Image

```bash
docker build -t resume-operator .
```

### Run the CLI in a container

```bash
docker run --rm \
  -e OPENAI_API_KEY=sk-your-key \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/input:/app/input \
  resume-operator run \
    --master /app/data/master_resume.yaml \
    --job /app/input/job.txt
```

### Run the engine server in a container

```bash
docker run --rm \
  -e OPENAI_API_KEY=sk-your-key \
  -p 7421:7421 \
  -v $(pwd)/data:/app/data \
  resume-operator-server --host 0.0.0.0 --port 7421
```

Bound at `0.0.0.0` inside the container, exposed on host port 7421. The desktop app's `VITE_SERVER_PORT` env var lets you point the frontend at this server during dev — useful when the engine and the GUI live on different machines.

### Dockerfile

The repo includes a `Dockerfile` at the root. The minimum it needs:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --no-dev --frozen
ENTRYPOINT ["uv", "run", "python", "-m", "resume_operator"]
```

For the server image, change the entrypoint to `["uv", "run", "resume-operator-server"]`.

### Docker Compose

```yaml
services:
  resume-operator-cli:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./input:/app/input
    command: run --master /app/data/master_resume.yaml --job /app/input/job.txt

  resume-operator-server:
    build: .
    env_file: .env
    entrypoint: ["uv", "run", "resume-operator-server", "--host", "0.0.0.0"]
    ports:
      - "7421:7421"
    volumes:
      - ./data:/app/data
```

```bash
# One-shot CLI run
docker compose run resume-operator-cli

# Long-running server
docker compose up resume-operator-server
```

---

## Desktop Installer (Windows)

Builds an `.msi` that installs the Tauri shell + the PyInstaller-bundled Python sidecar into the user's `Program Files\resume-operator`. The installed app runs end-to-end with no `uv` or Python on PATH.

Phase 6 of the desktop GUI roadmap. Spec: [`docs/issues/048-pyinstaller-tauri-msi.md`](../issues/048-pyinstaller-tauri-msi.md).

### Prerequisites (one-time, on the build machine)

- Python 3.12+ + uv (engine + PyInstaller)
- Node 20+ + pnpm 9+ (frontend bundler)
- Rust stable 1.85+ — `rustup update stable`
- **Visual Studio Build Tools** with the **"Desktop development with C++"** workload (required for MSVC's `link.exe`; without it, `cargo` fails with `link: extra operand …rcgu.o` because Git's GNU coreutils `link` shadows it). Install via Visual Studio Installer → Modify → Workloads → check that workload → Modify.

### One-shot release

```powershell
desktop/scripts/release.ps1
```

The script does, in order:

1. **`uv sync`** — installs PyInstaller alongside the engine deps.
2. **`uv run python pyinstaller/build.py`** — runs PyInstaller from [`pyinstaller/resume_operator_server.spec`](../../pyinstaller/resume_operator_server.spec), smoke-tests the produced binary by booting it on port 7421 and hitting `/health`, then copies it into `desktop/src-tauri/binaries/resume-operator-server-x86_64-pc-windows-msvc.exe` (Tauri's per-target naming convention).
3. **`pnpm install`** — fetches JS deps if not already present.
4. **`pnpm tauri:build`** — Tauri picks up the sidecar via `tauri.conf.json`'s `bundle.externalBin`, embeds it in the MSI, and produces:

```
desktop/src-tauri/target/release/bundle/msi/
└── resume-operator_0.1.0_x64_en-US.msi
```

The script reports the produced MSI path on success.

### What the installer ships

| Inside `Program Files\resume-operator\` | Purpose |
|---|---|
| `resume-operator.exe` | The Tauri shell (Rust binary, ~10 MB) |
| `resources\binaries\resume-operator-server-x86_64-pc-windows-msvc.exe` | The PyInstaller-bundled Python engine (~60 MB) |
| `resources\` (assets, icons) | App chrome |

Total install size: ~75 MB.

### Sidecar lifecycle

[`desktop/src-tauri/src/lib.rs`](../../desktop/src-tauri/src/lib.rs):

- **On launch** — `spawn_sidecar` resolves the bundled binary via Tauri's `shell.sidecar(...)`, spawns it with `["--port", "7421", "--host", "127.0.0.1"]`, and stores the `CommandChild` in a `SidecarState(Mutex<Option<...>>)` managed state.
- **On window close / app exit** — `terminate_sidecar` calls `child.kill()`. The sidecar never outlives the window.
- **In dev mode** — if the binary is missing (developer hasn't run `pyinstaller/build.py`), the helper logs a warning and tolerates it. The developer's `uv run resume-operator-server` in a separate terminal keeps working.

### App identity + signing posture

- **App identifier** — `security.klyro.resume-operator` (personal-use namespace, not distributed).
- **Unsigned by design** — `bundle.windows.certificateThumbprint` is `null`. Windows SmartScreen prompts on first run; the user clicks "More info → Run anyway". This is intentional for personal-use installs.
- **For shareable signed builds**, set the thumbprint in `tauri.conf.json` to a real cert (~$100/year for an authenticode cert) and re-run `tauri build`. Out of scope for v1.

### Sanity checks before releasing

```powershell
# Engine gates
uv run pytest                          # 344 tests
uv run ruff check src/ tests/
uv run mypy src/

# Desktop gates
cd desktop
pnpm typecheck
pnpm build

# PyInstaller standalone (skip Tauri)
cd ..
uv run python pyinstaller/build.py     # builds + smoke-tests the binary
```

Full release:

```powershell
desktop/scripts/release.ps1
```

Then install the produced MSI on a clean VM (or fresh Windows user without `uv` / Python on PATH) and run an end-to-end tailor cycle to confirm the bundle is self-contained.

### Cross-platform builds (out of scope but supported)

Tauri produces `.app` / `.dmg` on macOS, `.deb` / `.AppImage` on Linux. Each platform needs its own PyInstaller-bundled sidecar — `pyinstaller/build.py` already detects the target triple and copies into the right per-target name (`aarch64-apple-darwin`, `x86_64-unknown-linux-gnu`, etc.). To add a target:

1. Run `pyinstaller/build.py` on a machine of that platform.
2. Run `pnpm tauri:build` on the same machine.
3. The matching native installer drops into `desktop/src-tauri/target/release/bundle/`.

Cross-compiling Tauri itself across platforms is possible but out of scope here.

---

## Environment Variables (deployment-relevant)

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_PROVIDER` | No | `openai` (default), `anthropic`, `google`, `openrouter` |
| `LLM_MODEL` | No | Model name, default `gpt-4o` |
| `OPENAI_API_KEY` | If using OpenAI | Your OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Your Anthropic API key |
| `GOOGLE_API_KEY` | If using Google | Your Google AI API key |
| `OPENROUTER_API_KEY` | If using OpenRouter | Your OpenRouter API key |
| `LOG_LEVEL` | No | `INFO` (default), `DEBUG`, `WARNING` |

The desktop app's Settings screen exposes the same variables as a form. Writes persist to `.env` in the working directory the engine was launched from.

For the full list of tunables (ATS thresholds, weights, style path, etc.), see the [Environment Variables section in the README](../../README.md#environment-variables).

## Security Considerations

- **Never bake API keys into Docker images** — use env vars or `.env` files mounted at runtime.
- **Never commit `.env`** — it's in `.gitignore`.
- **Resume data is personal** — `data/` is git-ignored; mount it as a volume in Docker.
- **Use `.env` files** with `docker compose` instead of inline `-e` flags.
- **The desktop app's Settings GET masks API keys** (`sk-p…7890`) so the cleartext never round-trips back to the frontend. Only write paths can set new values.
- **The server binds to `127.0.0.1` by default** — no external exposure unless you explicitly pass `--host 0.0.0.0` (e.g., for the Docker server case above). When exposing externally, put it behind a reverse proxy with auth — there's no auth in the engine itself.

## Troubleshooting

### `"OPENAI_API_KEY not set"`

Your API key is missing or empty. Check your `.env` file or environment variables:
```bash
echo $OPENAI_API_KEY  # Should not be empty
```

### `"FileNotFoundError: resume.pdf"`

The resume file path is incorrect. Verify the file exists:
```bash
ls -la resume.pdf
```
In Docker, make sure the file is mounted into the container.

### `"ValueError: Unsupported LLM provider: xxx"`

The `LLM_PROVIDER` value must be one of: `openai`, `anthropic`, `google`, `openrouter`.

### `"PDF has no extractable text"`

The PDF is image-based (scanned document). Run it through OCR first (`ocrmypdf`).

### `"Model not found"` or API errors

Check that `LLM_MODEL` matches your provider:

- OpenAI: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`
- Anthropic: `claude-sonnet-4-6`, `claude-haiku-4-5`
- Google: `gemini-2.0-flash`, `gemini-2.5-pro`
- OpenRouter: any model from [openrouter.ai/models](https://openrouter.ai/models)

### `cargo` fails with `link: extra operand …rcgu.o`

Git's GNU coreutils `link` is shadowing MSVC's `link.exe`. Install Visual Studio's "Desktop development with C++" workload — see the [Prerequisites](#prerequisites-one-time-on-the-build-machine) section.

### PyInstaller bundle: `ModuleNotFoundError: No module named 'resume_operator.server'`

The server entry point used to pass uvicorn the app as a string (`"resume_operator.server.app:app"`); PyInstaller can't statically follow that. Phase 6 fixed this by importing the app object directly. If you see this error after a manual PyInstaller invocation, make sure you're using the latest [`src/resume_operator/server/main.py`](../../src/resume_operator/server/main.py) — non-reload mode imports `fastapi_app` by reference.

### Desktop app: `engine offline` indicator stays red

The sidecar didn't start. Two scenarios:

- **Dev mode** — the developer hasn't run `uv run resume-operator-server` in a second terminal.
- **Bundled mode** — the sidecar binary is missing or crashed. Open Tauri's devtools (debug builds open them automatically), check the log line for `"sidecar binary not found"` or `"failed to spawn sidecar"`. Re-run `pyinstaller/build.py` and rebuild the MSI.

### MSI installs but app fails to launch

Most likely the bundled sidecar can't reach the LLM provider — the binary is self-contained for Python, but the LLM call still hits the network. Confirm the user's `.env` has a valid API key + connectivity, or use the desktop Settings screen to set a new key.
