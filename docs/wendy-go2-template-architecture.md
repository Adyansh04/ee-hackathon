# Wendy Go2 Template Architecture

Sources inspected:

- https://github.com/wendylabsinc/templates/tree/main/python/go2-initial-test
- https://github.com/wendylabsinc/templates/tree/main/python/go2-rc
- https://github.com/wendylabsinc/templates/tree/main/python/go2-foxglove
- Local snapshot: `wendylabsinc/templates@9ab87ea`.

## Template Inventory

The Python template package currently contains three Go2-specific templates:

- `go2-initial-test`: large pre-hackathon hardware test board.
- `go2-rc`: browser teleoperation with motion API and onboard camera stream.
- `go2-foxglove`: live Foxglove visualization of LiDAR, pose, TF, state, UWB, and camera.

These are the best Wendy-native references for how to package Go2 apps.

## Shared Architectural Pattern

All Go2 templates use `network: host` through Wendy entitlements:

```json
{ "type": "network", "mode": "host" }
```

Reason: Unitree SDK, CycloneDDS, ROS2 discovery, WebRTC, and localhost service proxying need direct host networking. The Go2 network is usually in `192.168.123.0/24`, with a main controller IP around `192.168.123.161`.

## `go2-rc`

Purpose: remotely control Go2 EDU from a browser.

Services:

- `motion`: FastAPI API on port `3201`; wraps `unitree_sdk2_python` `SportClient`.
- `camera`: WebRTC-to-MJPEG bridge on port `8000`; connects to Go2 onboard camera.
- `rc`: web UI on `RC_PORT` default `3500`; proxies motion and camera via localhost.

Key endpoints:

- `POST /velocity`: non-blocking velocity command with watchdog.
- `POST /move`: timed move.
- `POST /stop`, `/stand`, `/sit`, `/lie`, `/hello`, `/dance`.
- `GET /state`: battery, IMU roll/pitch/yaw, foot force, tick.
- `GET /stream/color`: MJPEG camera stream.

Safety decisions worth copying:

- Velocity clamps: `vx ±0.6 m/s`, `vy ±0.4 m/s`, `yaw ±1.0 rad/s`.
- SDK calls run off the event loop with timeouts.
- Velocity watchdog stops the robot if commands stop arriving.
- Shutdown handler sends stop.

Build details:

- `motion` uses Ubuntu 22.04, CycloneDDS `0.10.5`, and pinned `unitree_sdk2_python`.
- `camera` uses Python 3.11 slim, OpenCV, `aiortc`, `unitree_webrtc_connect`, and CycloneDDS for LiDAR-derived proximity.

Important caveat: onboard Go2 WebRTC camera is effectively single-client; the Unitree phone app can steal the slot.

## `go2-foxglove`

Purpose: stream robot telemetry into Foxglove over one WebSocket.

Services:

- `bridge`: subscribes to DDS topics and serves Foxglove WebSocket on `FOXGLOVE_PORT`, default `8765`; receives camera JPEGs on ingest port `8766`.
- `camera`: WebRTC front camera client; forwards JPEGs to `bridge`.

Channels:

- `/go2/points`: LiDAR point cloud.
- `/go2/pose`: pose from sport mode state.
- `/tf`: `odom -> base_link`.
- `/go2/camera`: compressed image.
- `/go2/state`: JSON with lowstate/sport fields.
- `/go2/uwb`: JSON UWB state.

Design detail: bridge uses direct CycloneDDS IDL for `sensor_msgs/PointCloud2`, so it avoids a full ROS2 install for visualization.

Caveats marked in the source:

- Foxglove SDK API should be validated against the pinned version.
- Live Go2 EDU+ verification is still required.
- LiDAR topic assumes `rt/utlidar/cloud_deskewed`.

## `go2-initial-test`

Purpose: hardware go/no-go dashboard before the hackathon.

Services:

- `ui`: dashboard.
- `gpu`: CUDA/PyTorch/TensorRT smoke test.
- `lowstate`: IMU, foot contact, battery, joints, odometry, remote/UWB.
- `camera`: one WebRTC frame.
- `lidar`: one `PointCloud2` cloud.
- `mic`: ALSA record-level test.
- `speaker`: DDS audio receiver/manual confirmation.
- `motion`: manual SportClient movement test.
- `vui`: voice UI/head light/volume.
- `storage`: persistent volume read/write.
- `cloud`: internet/Wendy Cloud reachability.
- `extras`: ultrasonic/gimbal placeholders.
- `bt`, `btscan`: Bluetooth presence/scan.

Status contract:

- `GET /status` returns one or more results with `pass | fail | pending | manual | na`.
- `POST /run` reruns a test.

Ports:

- UI default `UI_PORT`.
- Backends use fixed host ports `3610` through `3622`.

Useful lessons:

- Auto-detect DDS bind address by routing to `GO2_IP` when possible.
- Bind DDS by IP address when the Go2 Jetson is multi-homed.
- Treat GPU and full test boards as heavy; pre-pull/pre-build images.
- `wendy run` group builds can be all-or-nothing; use `wendy run --service <name>` while iterating.

## What We Should Reuse

High confidence:

- `go2-rc` motion service pattern and watchdog.
- `go2-rc` WebRTC camera bridge pattern.
- `go2-foxglove` telemetry bridge for debugging.
- `go2-initial-test` lowstate/lidar/GPU checks as preflight diagnostics.

Medium confidence:

- Direct CycloneDDS `PointCloud2` readers without ROS2 for lightweight perception.
- Browser UI service proxying internal APIs over localhost.

Avoid copying blindly:

- Full `go2-initial-test` as the main app; it is too many containers for the MVP.
- Acrobatics/dance/action primitives in operator tasks.
- Multiple WebRTC clients. Centralize camera ownership.

## Suggested Template-Based App Shape

Start from `go2-rc`, then add services:

```text
go2-inspection-app/
  wendy.json
  motion/       # forked from go2-rc/motion
  camera/       # forked from go2-rc/camera
  mission/      # route/exploration/task runner
  perception/   # gauge/object/hazard pipeline
  dashboard/    # operator UI and reports
  viz/          # optional foxglove bridge
```

The first working demo should prove:

1. Robot can be stopped safely.
2. Camera frames arrive reliably.
3. Mission service can command bounded movement.
4. Perception service produces an inspection event.
5. Dashboard stores and displays evidence.
