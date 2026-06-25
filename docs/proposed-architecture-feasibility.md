# Proposed Hackathon Architecture and Feasibility

User plan:

```text
Frontier exploration
  -> create 3D map
  -> segment environment into sections
  -> assign section IDs and object lists
  -> user selects zone/object/task
  -> robot navigates closer and inspects
  -> Dimos enables complex natural-language tasks
```

## Feasibility Verdict

The plan is technically sound, but the complete version is ambitious for a hackathon. The risky part is not any single component; it is integrating all of them on real robot time:

- frontier exploration,
- robust SLAM,
- 3D semantic mapping,
- object inventory,
- natural-language planning,
- safe robot control,
- reporting.

Build the architecture so the full vision is possible, but demo a smaller end-to-end slice.

## Hardware Assumption

The robot-mounted compute is an NVIDIA Jetson Orin NX. Treat it as capable edge compute, but not as a workstation GPU. Keep navigation, mapping, segmentation, VLM reasoning, and report generation mostly sequential. Avoid running SAM, VLA/VLM inference, RTAB-Map export, local LLMs, and heavy visualization all at peak load while the robot is walking.

## Sequential Execution Model

Your proposed sequence is the right resource strategy:

```text
1. Explore or teach route
2. Save map, poses, and sensor evidence
3. Return to start/home
4. Run heavier segmentation and report generation
5. Show section/object inventory to operator
6. Operator selects targets
7. Generate ordered visit route
8. Execute visit route and inspect each target
```

Implementation detail: Go2-Inspector's current `inspection_node.py` runs SAM3 periodically on live RGB/depth frames. If you want post-exploration segmentation, either make the inspection node demand-triggered or record synchronized RGB/depth/pose keyframes during mapping and process those after the robot returns home. Without saved RGB/depth/TF evidence, SAM cannot reconstruct object detections from only an exported PLY map.

## Route and Goal Storage

For a ROS2/Nav2 implementation, store the operator-selected route as a mission file, then translate it into Nav2 action goals at runtime. Nav2 goals are execution messages, not the durable database.

Example persisted route:

```yaml
mission_id: inspect_selected_assets_001
map_id: demo_track_map_001
home_pose: { frame: map, x: 0.0, y: 0.0, yaw: 0.0 }
visits:
  - section_id: zone_a
    object_id: pressure_gauge_1
    nav_pose: { frame: map, x: 2.1, y: -0.4, yaw: 1.57 }
    task: read_gauge
  - section_id: zone_b
    object_id: exit_sign_1
    nav_pose: { frame: map, x: 4.0, y: 1.2, yaw: 0.0 }
    task: verify_presence
```

Runtime options:

- Send all poses via Nav2 `NavigateThroughPoses`.
- Send one `NavigateToPose` at a time, run inspection at each arrival, then continue.
- Prefer one-at-a-time execution for the hackathon because it makes retries, operator confirmation, and emergency stops simpler.

If using current DimOS-native navigation instead of ROS/Nav2, the persisted mission shape is still the same: section/object IDs plus poses/tasks. Only the runtime executor changes from Nav2 actions to DimOS planner/goal APIs.

## Recommended Hackathon MVP

Demo goal:

> “Wendy/Go2 can inspect known industrial sections, identify objects/instruments, go closer when asked, read or classify them, and generate an evidence-backed report.”

MVP pipeline:

```text
Manual/teach route or small frontier exploration
  -> map/section registry
  -> object snapshots per section
  -> operator chooses section/object
  -> robot navigates or is guided to checkpoint
  -> perception runs
  -> report is saved and shown
```

This still feels like your full plan, but avoids making autonomous exploration the demo’s single point of failure.

## Proposed System Layers

### 1. Robot I/O Layer

Responsibilities:

- Own the Go2 camera/WebRTC slot.
- Own motion commands.
- Enforce velocity clamps and watchdog stop.
- Publish state: battery, IMU, odometry, foot force, camera frame, LiDAR/point cloud.

Source to reuse: Wendy `go2-rc` and `go2-foxglove`.

### 2. Mapping and Navigation Layer

Responsibilities:

- Build map with RTAB-Map or lighter 2D SLAM.
- Publish `map`, `odom`, `base_link`, point clouds.
- Accept `go_to_pose` / `go_to_section` commands.
- Optionally run frontier exploration.

Source to reuse: Go2-Inspector `slam_nav_rtabmap.launch.xml`, `cmdvel_to_sport_bridge.cpp`, `odom_tf_bridge.cpp`, `frontier_explorer.cpp`.

Fallback: teach-and-repeat waypoints if Nav2/frontier exploration is unstable.

### 3. Semantic Section Layer

Responsibilities:

- Convert map into human-usable sections.
- Track objects/instruments per section.
- Provide stable IDs.

MVP implementation:

```yaml
sections:
  - id: pump_room_a
    name: Pump Room A
    pose: [1.4, -0.8, 0.0]
    objects:
      - id: pressure_gauge_1
        type: analog_gauge
        expected_range: [2.0, 4.0]
      - id: valve_1
        type: valve
```

Post-hackathon implementation:

- use map clustering/room segmentation,
- add object detections from SAM/YOLO/VLM,
- persist section inventory after each run.

### 4. Perception Layer

Responsibilities:

- Detect objects/hazards.
- Read instruments.
- Store evidence images.
- Return confidence and failure modes.

MVP:

- object detection/classification on camera frame,
- digital/analog instrument reading for one or two known instrument types,
- threshold rules.

Avoid overpromising “general all-instrument reading.” Pick the actual hackathon instruments once known.

### 5. Mission Layer

Responsibilities:

- Turn tasks into robot actions.
- Retry close-up image capture.
- Decide when to ask for confirmation.
- Build final report.

Example mission API:

```http
GET  /sections
GET  /sections/{id}/objects
POST /mission/inspect-section
POST /mission/inspect-object
POST /mission/stop
GET  /reports/latest
```

### 6. Dimos Copilot Layer

Responsibilities:

- Parse natural language.
- Call mission API skills.
- Summarize state and reports.

Do not let Dimos directly call unbounded Go2 action primitives. It should operate through safe, typed skills.

## Suggested WendyOS Service Graph

```text
dashboard
  -> mission
      -> motion
      -> camera
      -> perception
      -> nav
  -> reports/persist
viz/foxglove optional
dimos optional -> mission API
```

Initial `wendy.json` services:

```json
{
  "services": {
    "motion": { "context": "./motion", "entitlements": [{ "type": "network", "mode": "host" }] },
    "camera": { "context": "./camera", "entitlements": [{ "type": "network", "mode": "host" }] },
    "mission": {
      "context": "./mission",
      "dependsOn": ["motion", "camera"],
      "entitlements": [
        { "type": "network", "mode": "host" },
        { "type": "persist", "name": "inspection-data", "path": "/data" }
      ]
    },
    "dashboard": {
      "context": "./dashboard",
      "dependsOn": ["mission"],
      "entitlements": [{ "type": "network", "mode": "host" }]
    }
  }
}
```

Add `nav`, `perception`, and `dimos` after the core loop works.

## Phased Build Plan

### Phase 0: Hardware Preflight

Use Wendy `go2-initial-test` or copied tests to verify:

- camera,
- lowstate,
- LiDAR,
- motion stop,
- GPU,
- persistent storage,
- network.

### Phase 1: Safe Remote Inspection

- `motion` service from Wendy `go2-rc`.
- `camera` service from Wendy `go2-rc`.
- dashboard shows live camera and stop button.
- one button captures evidence and writes report JSON.

### Phase 2: Sections and Objects

- static `sections.yaml`;
- object inventory shown in dashboard;
- inspect selected object;
- store result and image.

### Phase 3: Navigation

- first try teach-and-repeat / manually recorded waypoints;
- then add Nav2 go-to-section if stable;
- keep manual fallback.

### Phase 4: Mapping and Exploration

- RTAB-Map 3D map;
- export PLY/2D map;
- optional frontier exploration.

For the sequential plan, record enough evidence during this phase:

- map-frame pose for each candidate viewpoint,
- RGB image,
- aligned depth image or point cloud,
- camera intrinsics,
- section/object candidate ID if known.

That evidence lets the robot return home before heavy SAM/VLM processing.

### Phase 5: Dimos Copilot

- Dimos calls only mission APIs;
- natural-language examples:
  - “Inspect pump room A.”
  - “Go to section 2 and check the pressure gauge.”
  - “Summarize abnormal findings.”

DimOS clarification: current `dimensionalOS/dimos` is not inherently tied to a ROS version for the Go2 WebRTC path. It can be used as a separate native system or as a copilot. Do not mix DimOS-native navigation and Nav2 as equal owners of robot motion in the same MVP.

## VLA/VLM Role

Use VLA/VLM-style models as bounded perception and reasoning tools, not direct motion controllers:

- At a waypoint, analyze the current image and decide whether the target is visible.
- Ask for a small controlled reframe such as "move 20 cm closer" only through a clamped mission API.
- Return structured results: `value`, `confidence`, `evidence_image`, `failure_reason`.

The safe control loop remains deterministic: navigation reaches a pose, perception evaluates, mission logic decides the next bounded action.

## Main Risks

- Robot time is scarce; autonomous mapping often eats time.
- WebRTC camera is single-client.
- ROS2/Nav2/RTAB-Map container will be heavy.
- External model APIs can fail on venue network.
- Semantic mapping is vague unless sections are defined explicitly.
- Pressing buttons requires extra hardware, not just Dimos.

## Decision

Build toward the full architecture, but make the demo depend on:

1. safe motion,
2. camera evidence,
3. section/object registry,
4. one reliable inspection task,
5. clean reporting.

Then add autonomous exploration, 3D mapping, and Dimos as multipliers rather than foundations.
