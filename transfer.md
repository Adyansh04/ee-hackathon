# Transfer Notes: DimOS Go2 Tester

Date: 2026-06-25

## Short Answer

You do **not** strictly need to build twice.

- **Local Docker Compose build** is optional. Use it to sanity-check Dockerfile/scripts on your laptop.
- **Wendy build/deploy** is the required path for the Jetson/WendyOS robot target. `wendy run` builds for the target architecture and pushes/deploys to `Fifi.local`.

Because this image is very large, build/deploy before robot testing time.

## Current App

App folder:

```text
apps/dimos-go2-tester/
```

Important files:

```text
apps/dimos-go2-tester/wendy.json
apps/dimos-go2-tester/docker-compose.yml
apps/dimos-go2-tester/docker-compose.local.yml
apps/dimos-go2-tester/.env.example
apps/dimos-go2-tester/.gitignore
apps/dimos-go2-tester/.dockerignore
apps/dimos-go2-tester/local/Dockerfile
apps/dimos-go2-tester/dimos/Dockerfile
apps/dimos-go2-tester/dimos/entrypoint.sh
apps/dimos-go2-tester/dimos/healthcheck.sh
apps/dimos-go2-tester/dimos/patch_dimos_runtime.py
apps/dimos-go2-tester/README.md
docs/dimos-real-robot-test-plan.md
```

## Current Dockerfile State

There are two Dockerfiles:

```text
apps/dimos-go2-tester/dimos/Dockerfile        # Wendy/Jetson ARM64
apps/dimos-go2-tester/local/Dockerfile        # local Docker Compose
```

Wendy Dockerfile starts with:

```dockerfile
FROM --platform=linux/arm64/v8 python:3.12-slim-bookworm
```

Local Compose uses `local/Dockerfile` with no platform pin, so it builds for the laptop's native architecture.

Reason:

- `wendy.json` must set `"platform": "linux/arm64"` for this Ubuntu/Jetson Wendy agent.
- Using `"platform": "wendyos"` creates an OCI image with `os: "wendyos"`, which the Linux container runtime cannot unpack.
- Omitting `platform` can make Wendy build for `ubuntu/arm64`, which has the same runtime manifest problem.
- The Wendy Dockerfile also forces the base image lookup to `linux/arm64/v8`.
- Wendy rejects build args containing slashes, so do not use `BASE_PLATFORM` with Wendy.
- Local Docker Compose uses a separate Dockerfile to avoid amd64/arm64 `exec format error`.

DimOS install and WebRTC patch:

```dockerfile
uv pip install --system "dimos[base,unitree]"
uv pip install --system --upgrade "unitree-webrtc-connect==2.1.2"
```

Do not reintroduce `DIMOS_EXTRAS=base,unitree` as a build arg. Wendy rejects comma-containing build args.

`patch_dimos_runtime.py` modifies the installed DimOS package at image build time:

- passes an optional AES key to `UnitreeWebRTCConnection`;
- creates a compatibility shim for `dimos.web.dimos_interface.api.server`;
- rewrites the Rerun dashboard to use the Jetson host instead of `localhost`;
- enables wildcard CORS for the Rerun gRPC bridge.

AES key sources, in order:

```text
UNITREE_AES_128_KEY
GO2_AES_128_KEY
/data/dimos/unitree_aes_key
```

## Current Wendy Config

`apps/dimos-go2-tester/wendy.json`:

```json
{
  "appId": "dimos-go2-tester",
  "version": "0.1.0",
  "platform": "linux/arm64",
  "services": {
    "dimos": {
      "context": "./dimos",
      "entitlements": [
        { "type": "network", "mode": "host" },
        { "type": "gpu" },
        { "type": "bluetooth" },
        { "type": "persist", "name": "dimos-data", "path": "/data/dimos" }
      ]
    }
  }
}
```

Wendy's current schema does not support per-service environment variables or per-service `run.args` here. Earlier `--user-args` tests did not reach this service reliably. The entrypoint now auto-probes common Go2 IPs and runs `basic` against `192.168.123.161` when it is reachable; otherwise it falls back to discovery.

For newer Go2 firmware, WebRTC may require a per-device AES key. For Wendy, prefer the persistent file path:

```text
/data/dimos/unitree_aes_key
```

## Current Compose Config

There are now two Compose files:

```text
apps/dimos-go2-tester/docker-compose.yml         # Wendy device deploy
apps/dimos-go2-tester/docker-compose.local.yml   # local laptop testing
```

`docker-compose.yml` is intentionally used by `wendy run`. Wendy's native multi-service `wendy.json` path does not pass service env or user args, but Wendy's Compose path forwards `environment:` entries to the container. The file uses bare env entries such as `DIMOS_MODE`, `ROBOT_IP`, and `OPENAI_API_KEY`, so export variables in the shell before `wendy run`.

Example agentic deploy:

```bash
cd apps/dimos-go2-tester
set -a
source .env
set +a
export DIMOS_MODE=agentic
wendy --device 192.168.123.18 run --debug
```

Local Compose uses `.env`, `docker-compose.local.yml`, `local/Dockerfile`, host networking, and privileged mode:

```yaml
build:
  context: .
  dockerfile: local/Dockerfile
privileged: true
cap_add:
  - NET_ADMIN
```

DimOS needs `NET_ADMIN` locally because it tries to enable loopback multicast and add an LCM multicast route.

The local `.env` file must **not** be committed. `.gitignore` now excludes it. A live-looking API key was seen in `.env`; rotate it if it was exposed or committed.

## Commands

Validate Wendy config:

```bash
cd apps/dimos-go2-tester
wendy json validate
```

Local laptop build/test:

```bash
cd apps/dimos-go2-tester
cp .env.example .env
docker compose -f docker-compose.local.yml up --build
```

If Docker has no `nvidia` runtime locally and you only want basic testing:

```bash
DOCKER_RUNTIME=runc docker compose -f docker-compose.local.yml up --build
```

Wendy deploy to Fifi/Jetson over Ethernet:

```bash
cd apps/dimos-go2-tester
export ROBOT_IP=192.168.123.161
export DIMOS_MODE=basic
wendy --device 192.168.123.18 run --debug
```

Watch logs:

```bash
wendy device logs --app dimos-go2-tester --service dimos --tail 50
```

## Test Flow

1. Start the basic DimOS test:

```bash
wendy --device 192.168.123.18 run --debug
wendy device logs --app dimos-go2-tester --service dimos --tail 50
```

2. Confirm the startup logs show:

```text
robot_ip=192.168.123.161
robot ping: ok
```

3. If WebRTC fails with `RSA key format is not supported`, `/offer` refused on `8081`, or `AesKeyRequiredError`, obtain the Unitree AES key and place it at:

```text
/data/dimos/unitree_aes_key
```

4. If basic works, try navigation/agentic by exporting `DIMOS_MODE=nav` or `DIMOS_MODE=agentic` before `wendy run`. For agentic, `OPENAI_API_KEY` must also be exported.

5. Open command center:

```text
http://<jetson-or-wendy-device-ip>:7779
```

## Runtime Modes

Entrypoint modes:

```text
discover
provision-wifi <ssid> <password>
basic <robot-ip>
nav <robot-ip>
agentic <robot-ip>
agentic-ollama <robot-ip>
spatial <robot-ip>
detection <robot-ip>
custom <robot-ip> <blueprint>
unitree-* <robot-ip>
shell
```

Important:

- `basic` runs `dimos run unitree-go2-basic`.
- `nav` runs `dimos run unitree-go2`.
- `discover` runs `dimos go2tool discover`.
- `detection` may require editing Dockerfile to install `dimos[base,unitree,perception]`; do not use comma build args with Wendy.

## Issues Already Fixed

### 0. Wendy native services did not receive env/user args

Symptoms:

```text
wendy --device 192.168.123.18 run --debug --user-args basic --user-args 192.168.1.42
...
[dimos-go2] mode=discover
[dimos-go2] ROBOT_IP is empty
```

Cause: the native multi-service `wendy.json` deploy path creates service containers without `Env`/`UserArgs`. Wendy's Compose deploy path does pass Compose `environment:` values.

Fix:

- added `apps/dimos-go2-tester/docker-compose.yml` for Wendy deploy;
- kept `wendy.json` as the companion file for entitlements;
- changed `entrypoint.sh` to pass DimOS global flags explicitly:

```text
dimos --robot-ip <ip> --viewer rerun-web --listen-host 0.0.0.0 run <blueprint>
```

Current stale app on the robot may still be old/basic. After redeploy, agentic mode should open:

```text
5555  WebInput
9990  MCP /mcp
```

### 1. Wendy rejected build arg

Error:

```text
invalid build arg "DIMOS_EXTRAS": value must contain only safe ASCII characters
```

Cause: `DIMOS_EXTRAS=base,unitree` contains a comma.

Fix: removed `DIMOS_EXTRAS` build arg and hardcoded:

```dockerfile
uv pip install --system "dimos[base,unitree]"
```

### 2. BuildKit `/etc/hosts` resource busy

Error:

```text
sed: can't move '/etc/hosts...' to '/etc/hosts': Resource busy
```

Fix:

```bash
docker buildx rm -f wendy
```

If needed:

```bash
sudo systemctl restart docker
docker buildx rm -f wendy 2>/dev/null || true
```

### 3. Wendy used `ubuntu/arm64`

Error:

```text
python:3.12-slim-bookworm: no match for platform in manifest
```

Cause: Wendy generated:

```text
--platform ubuntu/arm64
```

Fix: Wendy Dockerfile base image now forces:

```dockerfile
FROM --platform=linux/arm64/v8 python:3.12-slim-bookworm
```

Later finding: the better app-level fix is also to set:

```json
"platform": "linux/arm64"
```

in `wendy.json`, so the pushed OCI manifest is a normal Linux ARM64 image.

### 4. Wendy rejected `BASE_PLATFORM`

Error:

```text
invalid build arg "BASE_PLATFORM": value must contain only safe ASCII characters
```

Cause: `BASE_PLATFORM=linux/arm64/v8` contains slashes.

Fix:

- Removed `BASE_PLATFORM` from Wendy build path.
- Moved local Docker Compose to `docker-compose.local.yml`.
- Moved the local Dockerfile to `local/Dockerfile`.
- Removed default `docker-compose.yml` so Wendy does not choose the local Compose build path.

### 5. Local Compose `exec format error`

Error:

```text
exec /bin/bash: exec format error
```

Cause: local amd64 Docker tried to run ARM64 base image.

Fix: Compose now uses:

```yaml
context: .
dockerfile: local/Dockerfile
```

### 6. Wendy accidentally built the local Dockerfile

Error:

```text
load build definition from Dockerfile.local
python:3.12-slim-bookworm: no match for platform in manifest
```

Cause: Wendy selected the local-only Compose path instead of the Wendy service context. There must not be a default Compose file here:

```text
apps/dimos-go2-tester/docker-compose.yml
```

Local Compose must stay at:

```text
apps/dimos-go2-tester/docker-compose.local.yml
apps/dimos-go2-tester/local/Dockerfile
```

Current verified state: `apps/dimos-go2-tester/dimos/` contains `Dockerfile`, `.dockerignore`, `entrypoint.sh`, `healthcheck.sh`, and `patch_dimos_runtime.py`.

### 7. Device pull failed with `no match for platform`

Error:

```text
unpacking image "localhost:5000/dimos-go2-tester-dimos:latest":
reading manifest ... no match for platform in manifest
```

Cause: the image was pushed with a non-Linux OCI platform such as `wendyos/arm64` or `ubuntu/arm64`.

Fix: keep this in `wendy.json`:

```json
"platform": "linux/arm64"
```

Verified preflight after this change:

```text
Building and pushing image with Docker for linux/arm64...
```

### 8. Local Compose DimOS LCM permission failure

Error:

```text
RTNETLINK answers: Operation not permitted
CalledProcessError: Command '['ip', 'link', 'set', 'lo', 'multicast', 'on']'
```

Cause: DimOS tries to configure LCM multicast and socket buffers. The container lacked network administration privileges.

Fix for local Compose:

```yaml
privileged: true
cap_add:
  - NET_ADMIN
```

### 9. DimOS WebRTC auth failure on Go2

Observed runtime:

```text
robot_ip=192.168.123.161
robot ping: ok
HTTPConnectionPool(host='192.168.123.161', port=8081): connection refused
RSA key format is not supported
Could not get SDP from the peer
```

Network scan showed the robot responds on the robot LAN and `9991/tcp` is open while `8081/tcp` is closed. This points to newer Unitree local signaling. The image now upgrades `unitree-webrtc-connect` to `2.1.2` and patches DimOS to pass an optional AES key.

### 10. Agentic mode import failure

Observed runtime:

```text
ModuleNotFoundError: No module named 'dimos.web.dimos_interface'
```

Cause: `dimos==0.0.12.post2` references the newer `dimos.web.dimos_interface.api.server.FastAPIServer` path from the agentic web input module, but the PyPI wheel does not ship that subpackage.

Fix: `patch_dimos_runtime.py` creates a small compatibility shim at build time that exposes `FastAPIServer` from the wheel's existing `dimos.web.fastapi_server`.

The same patch makes `WebInput` text-only when no Whisper backend is installed. This avoids another agentic startup crash without pulling a large speech model into the hackathon image.

### 11. Web UI reached but behaved incorrectly

Causes found:

- DimOS defaults `GlobalConfig.viewer` to `rerun`, which redirects `/` to `/command-center` instead of the dashboard. The entrypoint now exports `VIEWER=rerun-web` unless overridden.
- DimOS defaults `listen_host` to `127.0.0.1`, which is not reachable from the laptop even with host networking. The entrypoint now exports `LISTEN_HOST=0.0.0.0` unless overridden.
- The packaged dashboard hardcoded iframe URLs to `localhost`, which points at the browser user's laptop, not the Jetson. The build-time patch rewrites it to use the Jetson host from `window.location.hostname`.
- Local Docker was missing `git-lfs`, which DimOS uses when resolving `command_center.html`. Both Dockerfiles now install `git-lfs`.

### 12. WebRTC connected but Rerun native viewer crashed

Observed runtime on the second test robot:

```text
[dimos] 🕒 LAN Signaling Method     : 🆕 con_notify (192.168.123.161:9991) (23:34:38)
...
[dimos] 🕒 Peer Connection State    : 🟢 connected     (23:34:38)
...
[dimos] Error: winit EventLoopError: [dimos] os error at ... neither WAYLAND_DISPLAY nor WAYLAND_SOCKET nor DISPLAY is set.
```

Cause: `unitree-webrtc-connect` successfully connected using `con_notify` on port 9991 even without an AES key (meaning some firmwares accept an empty/default key or allow a fallback!). However, DimOS then tried to open the `rerun` visualization window natively (GUI mode) which instantly fails inside the headless Wendy Jetson container.

Fix: the entrypoint now exports `VIEWER=rerun-web` and `LISTEN_HOST=0.0.0.0` unless already set. Package-file changes are done once at image build time by `patch_dimos_runtime.py`, not dynamically in `entrypoint.sh`.

Do not copy local `.env` files into `apps/dimos-go2-tester/dimos/`; `.dockerignore` now excludes them to prevent baking API keys or robot secrets into the image.

## Known Caveats

- Local x86 build previously produced an image around 18.8 GB.
- ARM64/Jetson build may expose Python wheel issues that did not appear on x86.
- The Wendy build is the important one for the robot; local Compose is only a sanity check.
- The Go2 WebRTC camera is usually single-client. Close the Unitree phone app.
- `Fifi.local` is the WendyOS device, not the Unitree Go2 IP.
- WendyOS Jetson over Ethernet: `192.168.123.18`.
- Go2 main controller over robot LAN: `192.168.123.161`.
- Newer Go2 firmware may need the per-device AES key for DimOS/WebRTC. Do not commit it.

## Verification Already Done

These checks passed after patches:

```bash
wendy json validate
docker compose -f docker-compose.local.yml --env-file .env.example config
bash -n apps/dimos-go2-tester/dimos/entrypoint.sh
```

Entrypoint parser was tested locally with a fake `dimos` command for:

```text
discover
basic 127.0.0.1
```

Local x86 Docker image was successfully built once before the later platform split, after adding:

```text
build-essential
portaudio19-dev
```

Those packages are required because `dimos[unitree]` pulls `pyaudio`.

## Immediate Next Step

Run:

```bash
cd apps/dimos-go2-tester
wendy --device 192.168.123.18 run --debug
```

If it builds and deploys, watch:

```bash
wendy device logs --app dimos-go2-tester --service dimos --tail 50
```

If the next run reaches the robot but reports an AES/WebRTC auth error, get the Unitree AES key and store it as `/data/dimos/unitree_aes_key` on the Wendy persistent volume before retrying.
