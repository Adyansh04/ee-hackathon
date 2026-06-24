# WendyOS + Unitree Go2 Hackathon Research

Last updated: 2026-06-24

## Challenge Summary

The hackathon target is an autonomous industrial inspection teammate on a Unitree Go2 with Jetson compute and WendyOS deployment. The strongest fit is not "remote camera on legs"; it should navigate a defined inspection scene, understand operator instructions, read industrial instruments, detect hazards, and report actionable findings with evidence.

## Recommended Project Directions

### 1. Instrument-Reading Inspection Teammate

Build a robot workflow that visits inspection points, captures instrument images, reads values, checks thresholds, and produces a report with photos, confidence, timestamp, and location/waypoint.

Why it fits: it directly matches the primary goal. A strong MVP can use semi-autonomous waypoint navigation plus robust perception and reporting.

Core pieces:
- Route/waypoint runner.
- Camera capture at each asset.
- Gauge/digital-display reading pipeline.
- Operator-facing report: `asset`, `reading`, `normal/alert`, `confidence`, `image`.
- Fallback behavior: ask for retake or human confirmation when confidence is low.

### 2. Teach-and-Repeat Inspection Routes

Let an operator drive the robot once, mark assets or hazards, then rerun the route with minimal hand-holding.

Why it fits: "trainable" and "low petting" are explicit scoring values. This can be demoed even if full SLAM is unstable.

Core pieces:
- Record waypoints, pose, camera frame, and task label.
- Replay route with stop-and-observe checkpoints.
- Edit task list through a simple config or dashboard.

### 3. Hazard Scout

Detect safety issues such as leaks, spills, smoke/steam, blocked walkways, missing PPE signs, open doors, or abnormal gauge readings.

Why it fits: useful and demo-friendly. It can combine object detection, segmentation, and rules.

Core pieces:
- Vision model for hazard categories available in the scene.
- Event log with image evidence.
- Alert severity and natural-language summary.

### 4. Operator Copilot Interface

Create a chat/voice interface: "Inspect pump station A", "read the pressure gauge", "what did you see?", "go back to the last valve."

Why it fits: makes the robot feel like a teammate. Keep actions bounded by a small command schema.

Core pieces:
- Speech/text command parser.
- Skill dispatcher for `go_to`, `inspect`, `read_gauge`, `report`, `return_home`.
- Audit log of every command and robot response.

### 5. Fleet/Slot-Aware Inspection Dashboard

Since the hackathon uses a shared fleet, build a dashboard that schedules robot slots, tracks robot health, shows current task state, and stores inspection reports.

Why it fits: less flashy than autonomy, but highly operator-friendly. Best as a supporting feature if the team has web/frontend bandwidth.

## Suggested MVP Architecture

Use WendyOS as the deployment wrapper for a Python app on the Jetson. Prefer a modular app:

- `robot_io`: Unitree control and sensor access through ROS2 SDK or WebRTC.
- `mission`: waypoint/task runner and retry policy.
- `perception`: instrument reader and hazard detector.
- `reporting`: JSON report plus lightweight local web UI.
- `safety`: max velocity, stop conditions, timeout, emergency-stop hook.

Fastest practical path:

1. Start with WebRTC or ROS2 high-level control, not low-level motor control.
2. Use teach-and-repeat/semi-autonomous navigation first.
3. Make perception and reporting excellent; judges will care if the robot does real operator work.
4. Add full Nav2/SLAM only if robot time and sensor stability allow it.

## Existing Repos and References

### WendyOS

- https://wendy.dev/ - WendyOS is an Apache-2.0 physical AI OS/toolchain for deploying edge AI apps to Jetson, Raspberry Pi, and similar devices. It supports containerized apps, USB-C deployment, Python/Rust/C++/TypeScript/Swift, camera/audio/GPU entitlements, rollback, and remote monitoring.
- https://docs.wendy.dev/latest/ - Official docs. CLI install: `curl -fsSL https://install.wendy.sh/cli.sh | bash`; normal app flow uses `wendy run`.
- https://github.com/wendylabsinc/samples - Official sample apps. Includes Python, C++, Rust, Swift, Node/TypeScript, simple servers, and DeepStream vision examples.
- https://github.com/wendylabsinc/WendyOS - WendyOS CLI/app manager repo.
- https://github.com/wendylabsinc/WendyOS-Builder - Yocto OS builds for Raspberry Pi and NVIDIA Jetson.

### Official Unitree

- https://github.com/unitreerobotics/unitree_sdk2 - Official C++ SDK v2. Ubuntu 20.04, CMake/GCC, examples in `example/`.
- https://github.com/unitreerobotics/unitree_sdk2_python - Official Python SDK2 interface. Depends on Python >=3.8, CycloneDDS 0.10.2, NumPy, OpenCV. Provides examples for high-level state/control such as `read_highstate.py` and `sportmode_test.py`.
- https://github.com/unitreerobotics/unitree_ros2 - Official ROS2 bridge/examples. Notes Ethernet setup around `192.168.123.99`, CycloneDDS config, and example nodes for Go2/B2 low state, sport mode state, wireless controller, high-level Go2 control, and bag recording.

### Unitree Go2 Community Stacks

- https://github.com/legion1581/unitree_webrtc_connect - Python WebRTC driver for Go2/G1. Useful if you want camera, audio, LiDAR, obstacle avoidance, and high-level sport controls over the same protocol as the Unitree mobile apps. No firmware modification required.
- https://github.com/abizovnuralem/go2_ros2_sdk - Unofficial ROS2 SDK for Go2 AIR/PRO/EDU over WebRTC Wi-Fi and CycloneDDS Ethernet. Includes URDF, real-time IMU/joint/foot-force topics, joystick, LiDAR PointCloud2, camera stream, Foxglove bridge, LaserScan, multi-robot support, `slam_toolbox`, Nav2, and COCO object detection.
- https://github.com/jizhang-cmu/autonomy_stack_go2 - Full autonomy stack for Go2 EDU using built-in L1 LiDAR and IMU. Includes SLAM, route planner, traversability, collision avoidance, and waypoint following.
- https://github.com/eppl-erau-db/amigo_ros2 - AMIGO: ROS2 Humble industrial inspection system on Unitree Go2 with Jetson, RealSense D435i/D455, RPLiDAR A3, Nav2, and containerized Isaac ROS workflow. Very relevant industrial-inspection reference.
- https://github.com/alexlin2/dimos-unitree - Agentive AI framework for Unitree Go2. Exposes ROS2/WebRTC action primitives, camera, IMU, state, and LiDAR to LLM-style agents with a local interface.
- https://github.com/abizovnuralem/go2_omniverse - Go2/G1 digital twin in NVIDIA Isaac Sim/Orbit with ROS2 camera/LiDAR streams, URDF sync, Nav2 + `slam_toolbox`, and RL environments.
- https://github.com/triple-zeropp/Triple-zero-robot-agent - Heterogeneous G1 + Go2 collaborative navigation example. Useful for multi-agent planning ideas, less directly needed for a single-dog hackathon.

### Instrument Reading

- https://arxiv.org/abs/2308.14583 - Analog gauge reading from synthetic data; pipeline detects key gauge structure and predicts angular reading.
- https://github.com/fuankarion/automatic-gauge-reading - Public repo attached to the above paper, but appears minimal as of this note.
- https://arxiv.org/abs/2404.08785 - Interpretable analog gauge reading in the wild; relevant for robust, failure-aware gauge-reading design.
- https://arxiv.org/abs/2005.03106 - Dial meter reading dataset/baselines; useful if the hackathon instruments include multi-dial meters.

### Recent Research Ideas

- https://arxiv.org/abs/2604.01708 - OpenGo: Go2 robot dog with skill library, dispatcher, self-validation, and human feedback. Good inspiration for a "skill dispatcher" architecture.
- https://arxiv.org/abs/2606.03340 - ROS2 autonomous navigation on Go2 EDU using RTAB-Map, AMCL/EKF fusion, Nav2 with A*/DWA; useful reference for navigation stack choices.
- https://arxiv.org/abs/2603.21723 - Triple-Zero path planning with Unitree G1 + Go2; code linked above.
- https://arxiv.org/abs/2606.14433 - Kine2Go dataset of Go2 gaits/motions; likely less useful for this hackathon unless doing locomotion learning.

## Current Build Bias

Best first build: **Instrument-Reading Inspection Teammate with teach-and-repeat routes**.

Use a simple mission file:

```yaml
route: pump-room-demo
waypoints:
  - id: pressure_gauge_1
    action: read_gauge
    expected_range: [2.0, 4.0]
  - id: valve_area
    action: detect_hazards
  - id: control_panel
    action: read_display
```

Demo story:

1. Operator says or clicks: "Inspect the pump room."
2. Go2 walks to each checkpoint.
3. At each checkpoint it captures evidence and runs the task.
4. It reports: "Pressure gauge 1 reads 4.8 bar, above expected range; confidence 0.82; image attached."
5. If uncertain, it says: "Reading uncertain; retaking image from closer distance."

This directly addresses useful, robust, low-petting, trainable, and wanted.
