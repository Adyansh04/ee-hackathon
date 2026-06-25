# DimOS Go2 Tester

Containerized DimOS runner for testing a real Unitree Go2 on the same WiFi/router as the Jetson or laptop running this app.

The safe first test is `DIMOS_MODE=basic`, which starts DimOS Go2 connection and visualization without jumping straight into autonomous navigation. After that works, use `nav`, `agentic`, `spatial`, or `detection`.

## Network Assumptions

- The Go2 and this container host are on the same LAN/WiFi router.
- You know the robot IP, or you can run discovery first.
- The Unitree phone app is closed so it does not steal the WebRTC camera session.
- Host networking is enabled; WebRTC, robot discovery, and the DimOS command center need direct host network access.

## Quick Start With Docker

Create an env file:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
ROBOT_IP=192.168.123.161
DIMOS_MODE=basic
```

Build and run:

```bash
docker compose -f docker-compose.local.yml up --build
```

If your Docker install does not expose the legacy `nvidia` runtime and you are only testing basic connectivity, set this in `.env`:

```bash
DOCKER_RUNTIME=runc
```

Local Compose uses `local/Dockerfile`, which builds for your laptop's native architecture. Wendy uses `dimos/Dockerfile`, which is pinned to ARM64 for the Jetson.

Local Compose also runs the container as privileged with `NET_ADMIN`; DimOS needs that to configure LCM multicast on loopback.

Build note: the validated local x86 Docker build installed `dimos==0.0.12.post2` and produced an image around 18.8 GB because current DimOS extras pull torch, Open3D, rerun, and CUDA-related wheels. Prebuild this image before your robot slot and make sure the Orin NX has enough free storage. The final ARM64/Jetson build must still be validated on the actual target because Python wheel availability can differ from x86.

Newer Go2 firmware may require a per-device AES key for WebRTC. This image upgrades `unitree-webrtc-connect` and patches DimOS to read the key from `UNITREE_AES_128_KEY`, `GO2_AES_128_KEY`, or `/data/dimos/unitree_aes_key`. The same build-time patch also fixes the missing agentic web import and rewrites the dashboard for remote LAN access. Do not commit the key.

Open the DimOS command center from another machine on the same router:

```text
http://<jetson-or-host-ip>:7779
```

## Run Modes

Set `DIMOS_MODE` in `.env`.

| Mode | DimOS command | Use |
| --- | --- | --- |
| `discover` | `dimos go2tool discover` | Find Go2 IP over BLE/LAN where available. |
| `basic` | `dimos run unitree-go2-basic` | First real-robot connectivity/stream test. |
| `nav` | `dimos run unitree-go2` | Mapping, costmap, planning, frontier exploration, browser command center. |
| `agentic` | `dimos run unitree-go2-agentic` | Natural-language agent; needs `OPENAI_API_KEY`. |
| `agentic-ollama` | `dimos run unitree-go2-agentic-ollama` | Local-agent path; needs Ollama reachable from the container. |
| `spatial` | `dimos run unitree-go2-spatial` | Navigation plus spatial memory. |
| `detection` | `dimos run unitree-go2-detection` | Object detection; likely needs a heavier image with perception/GPU extras. |
| `shell` | `bash` | Debug inside the container. |
| `custom` | `dimos run $DIMOS_BLUEPRINT` | Run any DimOS blueprint. |

## WendyOS Run

From this folder:

```bash
wendy --device 192.168.123.18 run --debug
```

The included `wendy.json` targets `linux/arm64` and provides the companion entitlements for the Compose deploy: host networking, GPU, Bluetooth for discovery/provisioning, and persistent storage at `/data/dimos`. `docker-compose.yml` is the Wendy deploy file; it forwards selected environment variables from the shell into the robot container. `docker-compose.local.yml` remains the laptop-only local build.

If no `ROBOT_IP` is provided, the entrypoint probes common Go2 IPs and currently selects `192.168.123.161` when reachable.

Wendy's Compose parser inherits only variables exported in the shell that launches `wendy run`. To run agentic mode without baking secrets into the image:

```bash
cd apps/dimos-go2-tester
set -a
source .env
set +a
export DIMOS_MODE=agentic
wendy --device 192.168.123.18 run --debug
```

For a quick basic-mode redeploy, use:

```bash
export ROBOT_IP=192.168.123.161
export DIMOS_MODE=basic
wendy --device 192.168.123.18 run --debug
```

If the app reaches the robot but fails with `RSA key format is not supported`, `AesKeyRequiredError`, or `/offer` refused on port `8081`, the robot likely needs its Unitree AES key for WebRTC. Place the key on the WendyOS persistent volume as `/data/dimos/unitree_aes_key`, or provide it through `UNITREE_AES_128_KEY` when running with local Docker.

Do not copy `.env` into `apps/dimos-go2-tester/dimos/`; that bakes secrets into the robot image. For local Docker, use `apps/dimos-go2-tester/.env`. For WendyOS, export secrets in the shell before `wendy run`, or put non-committed runtime overrides in `/data/dimos/.env` on the persistent volume.

Expected ports:

| Port | Mode | Purpose |
| --- | --- | --- |
| `7779` | basic/nav/agentic | DimOS dashboard and command center |
| `9876` | basic/nav/agentic with `rerun-web` | Rerun gRPC proxy |
| `9090` | basic/nav/agentic with `rerun-web` | Local Rerun web viewer, when the SDK starts it |
| `5555` | agentic only | Web text/audio input |
| `9990` | agentic only | MCP endpoint at `/mcp` |

Send agentic text over MCP once `9990` is open:

```bash
curl -s http://192.168.123.18:9990/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"agent_send","arguments":{"message":"look around and describe what you see"}}}'
```

For local Docker navigation mode:

```bash
DIMOS_MODE=nav docker compose -f docker-compose.local.yml up --build
```

The local `.env` file is for Docker Compose. Current Wendy schema does not expose per-service environment variables or per-service `run.args`, so avoid relying on runtime args for this multi-service app.

## Safety Checklist

1. Put the Go2 on a clear floor with a human near the physical stop control.
2. Start with `DIMOS_MODE=basic`.
3. Verify `ping $ROBOT_IP` from inside the container logs.
4. Verify command center loads on port `7779`.
5. Only then try `DIMOS_MODE=nav`.
6. Use small spaces and slow tests before frontier exploration.

## Data

Persistent app data is written to:

```text
/data/dimos
```

The Docker Compose app maps this to the named volume `dimos_data`. Wendy maps it through a `persist` entitlement.
