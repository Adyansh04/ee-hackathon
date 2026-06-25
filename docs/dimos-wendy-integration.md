# Dimos on WendyOS Integration Notes

Sources inspected:

- Current DimOS: https://github.com/dimensionalOS/dimos
- Current Go2 docs: `dimensionalOS/dimos/docs/platforms/quadruped/go2`
- Historical Unitree integration: https://github.com/alexlin2/dimos-unitree
- Local snapshots: `dimensionalOS/dimos@main` and `alexlin2/dimos-unitree@c07ec1e`.

## Summary

Current DimOS is not tied to a ROS distribution for the Go2 path. Its current docs describe Go2 navigation, mapping, and agentic control over WebRTC with "no ROS required"; ROS 2 is one optional transport, not the required runtime for the native Go2 stack.

This changes the earlier concern: the old `alexlin2/dimos-unitree` repo is ROS-heavy and aligned around Ubuntu 22.04/ROS Humble, but the current `dimensionalOS/dimos` repo supports Ubuntu 22.04/24.04, Python 3.12, and `dimos[base,unitree]` for Unitree WebRTC control without torch. For WendyOS, treat DimOS as either an alternate native navigation stack or an optional agent layer, not as something that must be installed inside the Go2-Inspector ROS container.

Use DimOS above a constrained mission API if natural-language control is needed. Do not let it directly own raw safety-critical motion in the hackathon demo.

## Current DimOS Go2 Stack

Current Go2 setup:

```bash
uv venv --python "3.12"
source .venv/bin/activate
uv pip install 'dimos[base,unitree]'
export ROBOT_IP=<go2-ip>
dimos run unitree-go2
```

The documented Go2 runtime includes:

- `GO2Connection`: WebRTC connection for LiDAR, video, and odometry.
- `VoxelGridMapper`: 3D voxel map generation, CUDA accelerated.
- `CostMapper`: converts 3D map into a 2D costmap.
- `ReplanningAStarPlanner`: A* navigation with replanning.
- `WavefrontFrontierExplorer`: autonomous frontier exploration.
- `RerunBridge` and `WebsocketVis`: browser visualization and command center.

Available blueprints include `unitree-go2-basic`, `unitree-go2`, `unitree-go2-agentic`, `unitree-go2-agentic-ollama`, `unitree-go2-spatial`, and `unitree-go2-detection`.

## OS, ROS, and Jetson Notes

DimOS current requirements list Ubuntu 22.04 as minimum and Ubuntu 24.04 as recommended. That is an OS support statement, not a ROS distro requirement.

Dependency tiers matter:

- `pip install dimos`: core streams, transports, CLI, maps.
- `pip install 'dimos[base,unitree]'`: Go2/G1 WebRTC support, no torch.
- `pip install 'dimos[base,unitree,perception]'`: adds detection/VLM pieces and needs GPU memory.
- `unitree-dds` and `dds`: optional DDS/CycloneDDS paths with extra system setup.

The hackathon robot has an NVIDIA Jetson Orin NX. Current DimOS docs list Jetson AGX Orin 32 GB as tested and Jetson Orin Nano 8 GB as experimental; Orin NX is between those classes, so the safe assumption is: basic Go2 control/navigation is plausible, but perception/VLM/SAM workloads should be run sequentially and measured on the actual device.

## Historical `alexlin2/dimos-unitree` Components

The older repo is still useful for understanding agent skills and Unitree integration, but it should not be treated as the current recommended DimOS install path.

Relevant folders:

- `dimos/agents`: OpenAI/planning agent classes, prompt/tool handling, memory.
- `dimos/robot`: generic robot control abstractions.
- `dimos/robot/unitree`: Go2 wrapper, ROS control, Unitree skills.
- `dimos/stream`: video providers and frame processing.
- `dimos/web`: FastAPI/Svelte web interface.
- `docker/unitree`: Dockerfiles and compose files for ROS, WebRTC, agents, and agent UI.

Unitree classes:

- `UnitreeGo2`: wraps ROS or WebRTC video/control. Enforces exactly one provider mode: `use_ros` XOR `use_webrtc`.
- `UnitreeROSControl`: subscribes to Go2 state/IMU/camera topics and publishes WebRTC requests through ROS.
- `MyUnitreeSkills`: exposes Unitree sport primitives and custom movement skills as callable agent tools.

## Available Skill Types

Dimos dynamically exposes many Unitree API primitives:

- Safe-ish posture/motion: `StandUp`, `StandDown`, `Sit`, `StopMove`, `RecoveryStand`, `BalanceStand`.
- Movement abstractions: `Move(distance)`, `Reverse(distance)`, `SpinLeft(degrees)`, `SpinRight(degrees)`, `Wait(seconds)`.
- Demo/unsafe actions: `Dance`, `FrontFlip`, `Handstand`, etc.

For this hackathon, explicitly block dynamic/acrobatic skills. Keep a whitelist:

- `inspect_zone`
- `go_to_section`
- `stop`
- `return_home`
- `read_instrument`
- `capture_evidence`
- `summarize_report`
- maybe `Move`, `Reverse`, `SpinLeft`, `SpinRight` only with small bounds.

## Historical Docker Shape

Dimos provides Docker setups:

- `docker/unitree/ros`: runs `go2_robot_sdk robot.launch.py`.
- `docker/unitree/ros_dimos`: runs ROS plus Dimos under supervisord.
- `docker/unitree/agents`: ROS plus planning agent.
- `docker/unitree/agents_interface`: ROS, agent, and web interface.
- `docker/unitree/webrtc`: lightweight WebRTC path.

They use Ubuntu 22.04, ROS Humble, host networking, optional GUI/RViz/X11, and large dependency sets. That stack is a different integration path from current DimOS WebRTC-native Go2 navigation.

## WendyOS Compatibility

Dimos can be packaged as a Wendy service:

```json
{
  "services": {
    "dimos": {
      "context": "./dimos",
      "entitlements": [
        { "type": "network", "mode": "host" },
        { "type": "gpu" },
        { "type": "persist", "name": "dimos-data", "path": "/data" }
      ]
    }
  }
}
```

If DimOS uses WebRTC-only Go2 control, it still needs host/LAN reachability to the robot and persistent storage for maps/logs. If it uses ROS2 or DDS transports, use host networking and test DDS discovery inside WendyOS. If it uses OpenAI, Ollama, or other model services, pass secrets safely at runtime and avoid baking keys into the image.

## Integration Pattern I Recommend

Do not let DimOS directly command raw Go2 actions in the main demo. Instead:

```text
Operator text/voice
  -> Dimos planner
  -> bounded mission API
  -> nav/mission service
  -> motion service with watchdog
  -> Go2
```

DimOS should call high-level skills:

- `list_sections()`
- `list_objects(section_id)`
- `inspect(section_id, object_id)`
- `navigate_to(section_id)`
- `read_gauge(object_id)`
- `generate_report()`

The mission service owns safety, route state, retries, and stop behavior.

## About “Press a Button”

DimOS can plan complex tasks if skills exist, but the Go2 alone cannot press a button unless the robot has a manipulator/end-effector or the task is reduced to touching with body/head, which is unsafe and unreliable. DimOS has manipulation abstractions, but the Go2-only setup does not provide a ready physical button-press capability.

For this hackathon, treat “press button” as future work unless hardware includes an arm/gripper and a tested skill.

## Risks

- Current DimOS native Go2 navigation and Go2-Inspector ROS/Nav2 are overlapping foundations; combining both early will waste time.
- Jetson Orin NX shared memory can become the bottleneck when mapping, SAM, VLM, and local LLMs run together.
- Agent execution can hallucinate unsafe action sequences unless strongly constrained.
- Cloud LLM features depend on venue internet and API keys.
- DDS/ROS interop is optional but adds discovery/network complexity inside containers.

## Verdict

Two feasible paths:

1. **ROS/Nav2 path:** Use Go2-Inspector ideas for RTAB-Map, Nav2 goals, SAM logs, and reports. Add DimOS later as a copilot that calls mission APIs.
2. **DimOS-native path:** Use current DimOS `unitree-go2` for WebRTC mapping/frontier exploration/navigation, then build a Wendy mission/reporting wrapper around its APIs.

Do not build both foundations at once. For the current plan, the Go2-Inspector/Nav2 route is easier to connect to the existing report pipeline; DimOS is best as the optional operator copilot after the deterministic inspection loop works.

Recommended order:

1. Build a deterministic inspection system first.
2. Expose a small HTTP skill API.
3. Add DimOS as an optional `copilot` service that calls only that API.
4. Demo natural-language commands through DimOS after the robot can already complete tasks without it.
