# WendyOS Deployment Notes

Sources inspected:

- Wendy docs: https://docs.wendy.dev/latest/
- Wendy Python templates: https://github.com/wendylabsinc/templates/tree/main/python
- Local research snapshot: `wendylabsinc/templates@9ab87ea` from 2026-06-24.

## Mental Model

WendyOS deploys apps as containers to the Jetson/edge device. A project normally contains:

- `wendy.json`: app identity, platform, services, entitlements, readiness, and hooks.
- `Dockerfile`: how each service image is built.
- App source files copied into the container.

For this hackathon, assume every robot-facing component must be containerized and run on the Go2-mounted NVIDIA Jetson Orin NX or WendyOS-managed target.

## Device Setup Flow

Developer machine:

```bash
curl -fsSL https://install.wendy.sh/cli.sh | bash
wendy --version
```

WendyOS target:

```bash
wendy discover
wendy device set-default
```

If running on an existing Linux/Jetson image instead of flashed WendyOS, install the agent on the target:

```bash
curl -fsSL https://install.wendy.sh/agent.sh | bash
sudo systemctl status wendy-agent
```

## Single-Container App Flow

Example from the official Python guide:

```bash
wendy init hello-world --target wendyos --language python --template simple-api \
  --var APP_ID=hello-world --var PORT=3001 --assistant skip --git-init no
cd hello-world
wendy run
```

`wendy run` builds the Docker image, deploys it to the selected device, starts it, and streams logs. Use:

```bash
wendy device apps list
wendy device logs --app <app-id>
```

## Multi-Service Options

There are two useful deployment styles.

### `wendy.json` Services

Official Go2 templates use this style. It is best when each container needs Wendy-specific entitlements such as `network`, `gpu`, `camera`, `audio`, `bluetooth`, or `persist`.

```json
{
  "appId": "go2-inspector",
  "version": "0.1.0",
  "platform": "linux",
  "services": {
    "motion": {
      "context": "./motion",
      "entitlements": [{ "type": "network", "mode": "host" }]
    },
    "dashboard": {
      "context": "./dashboard",
      "dependsOn": ["motion"],
      "entitlements": [{ "type": "network", "mode": "host" }]
    }
  }
}
```

Useful commands:

```bash
wendy run
wendy run --service motion
wendy run --service motion --deploy
wendy run --detach
wendy json validate
```

Important behavior: multi-service `wendy run` builds services in parallel, creates containers in dependency order, and multiplexes logs with service prefixes.

### Docker Compose

Wendy also supports `docker-compose.yml` / `compose.yml` projects. This is natural for ROS2 stacks split into bridge, navigation, perception, and UI containers.

```bash
wendy run --build-type compose
wendy run --build-type compose --detach
```

For ROS2 containers, use:

```yaml
network_mode: host
```

because DDS discovery and direct robot networking need host networking. Caveat from Wendy docs: compose `environment:` entries are parsed but not forwarded to device containers yet, so bake required variables into Dockerfiles, entrypoints, or commands.

## Entitlements We Likely Need

- `{ "type": "network", "mode": "host" }`: required for ROS2 DDS discovery, Unitree SDK/WebRTC, HTTP dashboards, and service-to-service localhost patterns.
- `{ "type": "gpu" }`: required for CUDA/PyTorch/TensorRT on Jetson.
- `{ "type": "camera" }`: needed for direct USB/CSI cameras such as RealSense; not necessarily needed for Go2 onboard WebRTC camera.
- `{ "type": "audio" }`: needed for local mic/speaker access.
- `{ "type": "bluetooth" }`: only if doing BLE/device discovery.
- `{ "type": "persist", "name": "...", "path": "/data" }`: store maps, logs, reports, model caches, and route definitions.

On the Orin NX, design services so heavy work can be turned on and off. Navigation/mapping should run during movement; SAM/VLM/report generation should usually run after the robot is stopped or back at home.

## Recommended Hackathon Deployment Shape

Start with `wendy.json` services, because the Wendy Go2 templates already use it and it handles service-specific hardware permissions clearly.

Minimum useful app group:

- `bridge`: Unitree/ROS2 bridge or WebRTC bridge.
- `mission`: waypoint/exploration/task state machine.
- `perception`: object/gauge/digital-display reading.
- `dashboard`: web UI, mission control, reports.
- Optional `viz`: Foxglove bridge for debugging.

If ROS2/Nav2 becomes heavy, collapse `bridge + nav + mission` into one ROS2 container to avoid DDS/shared-memory issues across containers.

## WendyOS Go2-Specific Cautions

- Build for ARM64/Jetson. Many images used by Wendy Go2 templates are arm64-only.
- Host ports are real device ports; avoid conflicts.
- WebRTC camera usually allows only one client. Close the Unitree phone app before using your app.
- ROS2 and Unitree DDS need the correct robot LAN interface/address.
- Keep heavy services optional. Full GPU + ROS2 + perception + web UI can pressure Jetson shared memory; use the sequential execution model in `proposed-architecture-feasibility.md`.
