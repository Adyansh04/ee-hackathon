# DimOS Real Robot Test Plan

This plan is for testing current DimOS on a real Unitree Go2 from the containerized app in `apps/dimos-go2-tester`.

## First Test Order

1. Put the Go2 and WendyOS Jetson/laptop on the same Go2 LAN. For the hackathon robot, Ethernet has used Jetson `192.168.123.18` and Go2 `192.168.123.161`.
2. Close the Unitree phone app to free the WebRTC camera session.
3. With Wendy, start with `wendy --device 192.168.123.18 run --debug`.
4. Confirm the logs show `robot_ip=192.168.123.161` and `robot ping: ok`.
5. If WebRTC fails with `/offer` refused on `8081`, `RSA key format is not supported`, or `AesKeyRequiredError`, obtain the Unitree AES key and place it at `/data/dimos/unitree_aes_key` on Wendy persistent storage.
6. Run `DIMOS_MODE=basic` with Docker Compose for local testing, or use the Wendy default basic mode on the robot, and confirm the command center opens.
7. Move to `nav` only after basic streams are stable.
8. Test agentic/detection modes last because they add model/API/GPU failure modes.

Prebuild warning: the local x86 Docker build produced an image around 18.8 GB. Build/pull the image before robot time, and validate the ARM64/Jetson build on the Orin NX before relying on it for the demo.

Local Docker Compose uses `docker-compose.local.yml` plus `local/Dockerfile` and runs privileged with `NET_ADMIN` so DimOS can configure LCM multicast. Wendy uses only `dimos/Dockerfile`, with `wendy.json` set to `"platform": "linux/arm64"` so the Jetson receives a normal Linux ARM64 image. Do not add platform build args because Wendy rejects slash-containing build arg values.

## Features You Can Test

### Connectivity and Provisioning

- `dimos go2tool discover`: robot discovery over BLE/LAN where available.
- `dimos go2tool connect-wifi`: provision robot WiFi if Bluetooth access is available.
- `ROBOT_IP` connectivity from the container host.
- WebRTC connection to a stock Go2 Pro/Air without ROS or jailbreak.
- Newer Go2 firmware may require its per-device AES key for WebRTC.

### Basic Go2 Streams

Mode: `DIMOS_MODE=basic`

- Video stream.
- LiDAR/voxel stream.
- Odometry/pose stream.
- Robot connection stability over router WiFi.
- Browser visualization and command center exposure on port `7779`.

### Native Navigation Stack

Mode: `DIMOS_MODE=nav`

- `GO2Connection` WebRTC data path.
- `VoxelGridMapper` 3D voxel mapping.
- `CostMapper` 3D-to-2D costmap generation.
- `ReplanningAStarPlanner` click-goal navigation.
- `WavefrontFrontierExplorer` frontier exploration.
- Browser map, pose, costmap, and path monitoring.

### Agentic Control

Mode: `DIMOS_MODE=agentic`

- Natural-language robot commands through DimOS.
- LLM agent access to robot camera/LiDAR/spatial streams.
- MCP-style skill listing and skill calls if exposed by the running blueprint.
- `humancli` interaction from an interactive shell in the same container.

This requires `OPENAI_API_KEY` unless using the Ollama path.

### Local Agent Path

Mode: `DIMOS_MODE=agentic-ollama`

- Local LLM-backed agent control if an Ollama server and model are reachable.
- Useful when venue internet is unreliable.

Expect this to be resource-sensitive on Orin NX.

### Spatial and Detection Modes

Modes: `DIMOS_MODE=spatial`, `DIMOS_MODE=detection`

- Spatial memory behavior.
- Object detection blueprint behavior.
- GPU/model download behavior on Orin NX.

Detection may require editing the Dockerfile install line to include perception extras and rebuilding:

```bash
uv pip install --system "dimos[base,unitree,perception]"
```

The Wendy build path intentionally avoids a `DIMOS_EXTRAS` build arg because Wendy rejects comma-containing build-arg values.

## Features You Should Not Treat as Ready From This App

- ROS2/Nav2 validation. This app uses current DimOS native Go2/WebRTC blueprints, not the Go2-Inspector ROS stack.
- Go2-Inspector SAM3 report generation. That is a separate ROS/RGB-D/SAM pipeline.
- RealSense camera topics. DimOS Go2 WebRTC uses Go2 streams, not the Go2-Inspector RealSense topic layout.
- Unitree DDS low-level testing unless you build a separate image with `unitree-dds`/DDS setup.
- Physical button pressing. The Go2 needs a manipulator or tested contact tool for that.
- Multiple simultaneous camera clients. The Go2 WebRTC camera is effectively single-client.
- Unsupervised frontier exploration in cluttered spaces. Keep a human safety operator present.

## Features You Cannot Test Without Extra Setup

- Perception/VLM-heavy detection if the image is built only with `base,unitree`.
- Local LLM control unless Ollama and a model are installed and reachable.
- Cloud agent control without `OPENAI_API_KEY` and reliable internet.
- BLE WiFi provisioning unless the container has Bluetooth access from Wendy/Docker.
- Persistent premap/relocalization workflows until you confirm where DimOS writes map artifacts in this container.

## Practical Hackathon Verdict

Use this DimOS app to answer three questions quickly:

1. Can DimOS connect to the robot reliably over the event router?
2. Are video, LiDAR, odometry, and basic visualization stable enough on Orin NX?
3. Is DimOS native navigation good enough to become the base, or should it stay as a copilot above the Go2-Inspector/Nav2 route?

If `basic` and `nav` work cleanly, DimOS-native navigation is worth a serious trial. If they are unstable, keep DimOS as a natural-language/copilot layer and build the inspection MVP on the deterministic ROS/Nav2 or waypoint stack.
