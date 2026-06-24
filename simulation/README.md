# Go2 MuJoCo sim — velocity control + head RealSense (no RL)

Drive the **official Unitree Go2** (MuJoCo Menagerie) by **body velocity** — linear x,
linear y, yaw rate — with a head-mounted **official RealSense D435i** (RGB + depth).
Locomotion is a scripted **omnidirectional trot** (CPG + 3-DOF inverse kinematics + PD
torque control). **No RL, no training, no DDS, no ROS, no keyboard teleop.**

The official Go2 + RealSense models are pulled automatically via `robot_descriptions`
(MuJoCo Menagerie) and composed at runtime with `MjSpec` (RealSense rigidly attached to
the head + a forward-looking `head_cam`). `mujoco` only does physics; `go2_velocity.py`
is the controller.

## Setup (one-time)

Uses [`uv`](https://docs.astral.sh/uv/) for a clean, isolated env (no system Python
touched). Install uv with `curl -LsSf https://astral.sh/uv/install.sh | sh` if needed.

```bash
cd simulation
uv venv mjenv --python 3.12
uv pip install --python mjenv/bin/python -r requirements.txt
```

(Plain `python -m venv mjenv && mjenv/bin/pip install -r requirements.txt` works too.)

## Run

```bash
cd simulation

# GUI — watch it move at a commanded velocity (press Tab in the viewer for head_cam):
./mjenv/bin/python go2_velocity.py --vx 0.3 --vyaw 0.4 --view

# Headless — print odometry + save the head RealSense RGB and depth:
./mjenv/bin/python go2_velocity.py --vx 0.3 --headless --seconds 6 \
    --snapshot head_rgb.png --depth-snapshot head_depth.png
```

CLI: `--vx` (forward m/s) · `--vy` (left m/s) · `--vyaw` (yaw rad/s) · `--seconds`
`--view` / `--headless` · `--snapshot` / `--depth-snapshot`.

## ROS 2 node — publish velocities, the sim moves (`go2_ros_node.py`)

A ROS 2 node wraps the sim:
- **subscribes** `/cmd_vel` (`geometry_msgs/Twist`) → body velocity (`linear.x`, `linear.y`, `angular.z`)
- **publishes** `/go2/odom` (`nav_msgs/Odometry`), `/go2/joint_states` (`sensor_msgs/JointState`),
  `/go2/camera/image_raw` (`sensor_msgs/Image`, rgb8), `/go2/camera/depth` (`sensor_msgs/Image`, 32FC1)

Needs ROS 2 (tested on **Jazzy**) plus the pip deps. Make the venv ROS-aware with
`--system-site-packages` so it sees the system `rclpy`:

```bash
cd simulation
source /opt/ros/jazzy/setup.bash                       # your distro
uv venv rosenv --system-site-packages --python 3.12
uv pip install --python rosenv/bin/python -r requirements.txt

# terminal A — run the sim node (add --view for the MuJoCo window):
source /opt/ros/jazzy/setup.bash
./rosenv/bin/python go2_ros_node.py

# terminal B — just publish velocities:
source /opt/ros/jazzy/setup.bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
    "{linear: {x: 0.3, y: 0.0}, angular: {z: 0.4}}" -r 10
ros2 topic echo /go2/odom            # watch it move
```

`go2_ros_node.py` flags: `--view`, `--no-camera`, `--seconds N` (auto-stop).

## Use as a library

```python
from go2_velocity import Go2Velocity
c = Go2Velocity(view=False)
c.set_velocity(vx=0.3, vy=0.0, vyaw=0.5)   # m/s, m/s, rad/s
c.run(seconds=5)                            # or call c.step() in your own loop
rgb   = c.render_rgb()                       # HxWx3 uint8 from the head RealSense
depth = c.render_depth()                     # HxW   float metres
x, y, z = c.odom()
```

## Verified (headless, official model)

| Command | Result |
|---|---|
| stand | no drift (dx ≈ 0) |
| `vx 0.3` | **+0.24 m/s forward** |
| `vx -0.2` | −0.21 m/s back |
| `vy ±0.2` | **±0.16 m/s strafe** |
| `vyaw ±0.6` | **±0.5 rad/s turn in place** |
| `vx + vyaw` | curved arc |

All stay upright (body z ≈ 0.27). `head_rgb.png` / `head_depth.png` are example outputs.

## How it works
- **3-DOF analytic IK** per leg incl. the hip abduction offset (0.0955 m); validated
  against the official home pose (hip 0, thigh 0.9, calf −1.8) and via FK (`+px → +x`).
- **Omnidirectional trot**: each foot's stance sweep = −(body velocity + yaw × r_foot),
  so vx/vy/vyaw map to translate/strafe/rotate. Diagonal legs (FL+RR, FR+RL) a half-cycle apart.
- **PD torque control** (Menagerie uses motor actuators): τ = KP·(q_des − q) − KD·q̇,
  clamped to torque limits. Params auto-tuned: `KP=250` (firm stance → no scuff) `KD=6`
  `GAIT_FREQ=2.0` `STEP_HEIGHT=0.10` `STAND_H=0.27`.

## Tuning knobs (top of `go2_velocity.py`)
`KP`/`KD` (stiffness) · `GAIT_FREQ` · `STEP_HEIGHT` · `STAND_H` · `SWEEP_MAX` (max speed) ·
`CAM_POS`/`CAM_FOVY` (head camera). If it stumbles, raise `KP` or lower `GAIT_FREQ`.

## Note
The velocity API (`set_velocity(vx, vy, vyaw)`) intentionally matches the real Unitree
`SportClient.Move(vx, vy, vyaw)` signature, so control/perception code written against
this sim ports cleanly to the real Go2. The trot itself is sim-only (the real dog walks
via its own onboard controller).
