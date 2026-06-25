# Go2-Inspector Evaluation

Source inspected:

- https://github.com/amberhandal/Go2-Inspector
- Local snapshot: `amberhandal/Go2-Inspector@281ccca`, commit date 2026-03-24.

## Summary

`Go2-Inspector` is highly relevant to the plan. It is an autonomous building inspection system for Unitree Go2 using ROS2, Nav2, RTAB-Map, frontier exploration, RealSense depth camera topics, SAM-based object detection, change detection, and report export.

It is not a drop-in WendyOS app yet. It is a ROS2 package expecting a full ROS workspace, Unitree ROS2 dependencies, and a separate SAM 3 HTTP service. It is best treated as a reference architecture and possible code source, then containerized selectively.

## What It Provides

Core ROS2 package: `go2_navigation`.

Important nodes:

- `cmdvel_to_sport_bridge.cpp`: bridges Nav2 `/cmd_vel` into Unitree Sport API requests on `/api/sport/request`.
- `odom_tf_bridge.cpp`: converts `/utlidar/robot_odom` into `odom -> base_link` TF and republishes `/odom`.
- `pointcloud_refiner.cpp`: filters/downsamples/clusters point cloud data into `/refined_cloud`.
- `frontier_explorer.cpp`: finds occupancy-grid frontiers and sends Nav2 goals.
- `navigation_node.cpp`: simple `/walk` and `/stop` services for basic movement.
- `joint_state_bridge.cpp`: converts Unitree lowstate to joint states.

Python tools:

- `inspection_node.py`: captures RGB/depth, calls SAM 3, localizes detections into map frame, publishes markers, logs JSON.
- `change_detector.py`: compares detections across runs.
- `map_export.py`: renders annotated 2D building/floor maps.
- `ply_marker_injector.py`: inserts markers into 3D PLY output.
- `inspection_report.py`: generates PDF comparison reports.
- `watchdog_run.py`: lifecycle wrapper that starts launch, then exports map/database/PLY/report on shutdown.

Detailed log/report/SAM3 format: see [Go2-Inspector Report and SAM3 Data Flow](./go2-inspector-report-and-sam3.md).

Launch/config:

- `slam_nav_rtabmap.launch.xml`: main launch for RTAB-Map, Nav2, exploration, inspection.
- `nav2_params_rtabmap.yaml`: Nav2 controller/planner/costmap settings.
- URDF includes Go2 body, front camera, and static transforms.

## Architecture Fit

This repo matches your full idea almost exactly:

```text
Go2 sensors -> ROS2 topics -> RTAB-Map / Nav2 -> frontier explorer
             -> inspection_node -> SAM service -> object logs
             -> map_export / PDF reports
```

Especially useful pieces for us:

- RTAB-Map + Nav2 launch wiring.
- `frontier_explorer.cpp` algorithm and state machine.
- `cmdvel_to_sport_bridge.cpp` for Nav2-to-Go2 motion.
- Report/export scripts.
- Concept of baseline-vs-current change detection.

## Feasibility Under WendyOS

Feasible, but heavy. To deploy through WendyOS, build a ROS2 container that contains:

- ROS2 distro matching the target base image.
- Nav2.
- RTAB-Map.
- PCL dependencies.
- Unitree ROS2 and SDK2 repos from `deps.repos`.
- `go2_navigation` package.

Run with host networking:

```yaml
network_mode: host
```

or Wendy service entitlement:

```json
{ "type": "network", "mode": "host" }
```

Persist maps/reports:

```json
{ "type": "persist", "name": "inspection-data", "path": "/data" }
```

## Risks and Gaps

High risk:

- Full ROS2 + Nav2 + RTAB-Map + SAM + Dimos is too much for first MVP.
- README says ROS2 Kilted; Dimos Docker uses Humble; Wendy Go2 templates use lighter non-ROS services. Aligning distros will take time.
- SAM 3 server is external by default (`sam3_url`), so offline demo reliability depends on localizing or replacing that service.
- RealSense topics are assumed: `/camera/color/image_raw`, `/camera/aligned_depth_to_color/image_raw`, and restamped variants. Confirm hackathon hardware actually includes RealSense.
- `CMakeLists.txt` installs only `scripts/pointcloud_restamper.py` under `install(PROGRAMS ...)`; several README-described scripts may need install fixes before `ros2 run` works cleanly.
- Nav2 tuning depends on LiDAR frame pitch. README notes real robot UTLidar pitch must be `2.8782 rad`; wrong transform causes phantom obstacles.

Medium risk:

- Frontier exploration chooses closest valid frontier. This is simple and usable, but can get stuck around clutter or bad maps.
- Reports are strong, but industrial instrument reading is not built in.
- `inspection_report_llm.py` is marked TODO/test-needed.

Low risk:

- Map/report export utilities are straightforward and valuable even if autonomous exploration is not fully stable.

Sequential-plan note:

- The current SAM3 path is live-frame RGB/depth detection, not offline segmentation of an exported PLY map.
- For post-exploration processing, record synchronized RGB/depth/camera-info/pose keyframes during exploration or keep the ROS graph alive while running the inspection pass.
- If the robot returns home and the ROS launch shuts down before segmentation, the existing scripts can still export maps/reports, but they cannot invent object detections unless detections were already logged.

## Recommended Use

Use `Go2-Inspector` in phases:

1. Steal architecture, launch ideas, and export/report scripts.
2. Bring up minimal ROS2 container with Unitree topics and Foxglove/RViz.
3. Add RTAB-Map mapping only.
4. Add Nav2 goal navigation.
5. Add frontier exploration if mapping and Nav2 are stable.
6. Add inspection perception as a separate service.

For the hackathon demo, do not make frontier exploration the only path. Keep a waypoint/teach-and-repeat mode as fallback.

## Containerization Plan

Option A: one ROS2 container.

Best for hackathon reliability. Put Unitree bridge, RTAB-Map, Nav2, and `go2_navigation` in one image. This avoids cross-container DDS/shared-memory issues.

Option B: split services.

```text
ros-bridge   -> Unitree topics
nav-stack    -> RTAB-Map + Nav2 + frontier explorer
inspection   -> SAM/gauge/object detection
dashboard    -> web UI/reports
```

This is cleaner long-term but higher integration risk.

## Verdict

Good and feasible as a reference. Too large to adopt wholesale. The smart move is to extract the navigation/mapping/reporting ideas, containerize a minimal ROS stack, and keep the actual hackathon MVP narrower: a robot that can inspect known sections and generate evidence-backed reports.
