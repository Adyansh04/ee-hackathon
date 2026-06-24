#!/usr/bin/env python3
"""
Velocity control for the OFFICIAL Unitree Go2 (MuJoCo Menagerie) + a head-mounted
RealSense D435i camera — NO RL, NO teleop.

You command a body velocity (linear x, linear y, yaw rate); a scripted
omnidirectional trot gait + per-leg inverse kinematics + PD torque control drives
the official Go2. The official Menagerie RealSense D435i is attached to the head
(via MjSpec) with a `head_cam`, so you can render RGB + depth for perception.

API:
    c = Go2Velocity(view=False)
    c.set_velocity(vx=0.3, vy=0.0, vyaw=0.5)      # m/s, m/s, rad/s
    c.run(seconds=5)                               # or c.step() in your own loop
    rgb   = c.render_rgb()                          # HxWx3 uint8 from head_cam
    depth = c.render_depth()                        # HxW   float metres

CLI:
    .../mjenv/bin/python go2_velocity.py --vx 0.3 --vyaw 0.4 --view
    .../mjenv/bin/python go2_velocity.py --vx 0.3 --headless --seconds 5 \
        --snapshot head_rgb.png --depth-snapshot head_depth.png
"""
from __future__ import annotations
import argparse, math, os
import numpy as np
import mujoco
import mujoco.viewer

from robot_descriptions import go2_mj_description as _G
_MEN = os.path.dirname(os.path.dirname(_G.MJCF_PATH))
GO2_SCENE = os.path.join(os.path.dirname(_G.MJCF_PATH), "scene.xml")   # robot + floor
RS_MODEL  = os.path.join(_MEN, "realsense_d435i", "d435i.xml")         # official D435i

# --- official Go2 geometry (from go2.xml) ---
L_OFF = 0.0955    # hip-roll -> thigh lateral offset
L_TH  = 0.213     # thigh length
L_CA  = 0.213     # calf length
LEGS  = ["FL", "FR", "RL", "RR"]                   # actuator/joint order (leg-grouped)
SIDE  = {"FL": +1, "FR": -1, "RL": +1, "RR": -1}
HIP_XY = {"FL": (0.1934, 0.0465), "FR": (0.1934, -0.0465),
          "RL": (-0.1934, 0.0465), "RR": (-0.1934, -0.0465)}
PHASE_OFF = {"FL": 0.0, "FR": 0.5, "RL": 0.5, "RR": 0.0}   # trot diagonals

# --- gait + control params (auto-tuned via headless sweep; see README) ---
# tuned: KP=250 stiff stance (no scuff) -> fwd ~0.24 m/s, strafe ~0.16 m/s, drift ~0.
STAND_H     = 0.27
GAIT_FREQ   = 2.0
DUTY        = 0.5
STEP_HEIGHT = 0.10
SWEEP_MAX   = 0.18
KP          = 250.0
KD          = 6.0

# --- head camera mount (on the front of the base) ---
CAM_POS  = [0.30, 0.0, 0.07]   # relative to base (head/front-top)
CAM_FOVY = 58.0                # vertical FOV (deg)


def build_model():
    """Compose the official Go2 + floor with the official RealSense D435i attached
    to the head and a forward-looking `head_cam`. Returns a compiled MjModel."""
    spec = mujoco.MjSpec.from_file(GO2_SCENE)
    rs   = mujoco.MjSpec.from_file(RS_MODEL)
    base = spec.body("base")
    frame = base.add_frame()
    frame.pos = [0.30, 0.0, 0.06]                 # mount point on the head
    frame.attach_body(rs.body("d435i"), "rs_", "")  # rigid attach (no extra DOF)
    cam = base.add_camera()
    cam.name = "head_cam"; cam.fovy = CAM_FOVY; cam.pos = CAM_POS
    R = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=float)  # look +x, up +z
    q = np.zeros(4); mujoco.mju_mat2Quat(q, R.flatten()); cam.quat = q
    return spec.compile()


def leg_ik(px, py, pz, side):
    """3-DOF analytic IK. Foot (px fwd, py left, pz up) relative to the hip-roll
    joint, body frame. Returns (hip, thigh, calf). Validated against the official
    home pose and via forward kinematics (+px -> foot at +x)."""
    yz = math.hypot(py, pz); yz = max(yz, abs(L_OFF) + 1e-4)
    q_hip = math.atan2(pz, py) + math.acos(max(-1.0, min(1.0, side * L_OFF / yz)))
    w = pz * math.cos(q_hip) - py * math.sin(q_hip)
    r = math.hypot(px, w); r = min(max(r, abs(L_TH - L_CA) + 1e-3), L_TH + L_CA - 1e-3)
    cos_k = (L_TH * L_TH + L_CA * L_CA - r * r) / (2 * L_TH * L_CA)
    q_calf = math.acos(max(-1.0, min(1.0, cos_k))) - math.pi
    q_thigh = math.atan2(-px, -w) - math.atan2(L_CA * math.sin(q_calf),
                                               L_TH + L_CA * math.cos(q_calf))
    return q_hip, q_thigh, q_calf


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class Go2Velocity:
    def __init__(self, view=False):
        self.m = build_model()
        self.d = mujoco.MjData(self.m)
        self.dt = self.m.opt.timestep
        self.vx = self.vy = self.vyaw = 0.0
        self.phase = 0.0
        self.foot_xy = {lg: (HIP_XY[lg][0], HIP_XY[lg][1] + SIDE[lg] * L_OFF) for lg in LEGS}
        self.tau_lim = self.m.actuator_ctrlrange[:, 1].copy()
        self._rgb = self._depth = None
        mujoco.mj_resetDataKeyframe(self.m, self.d, 0)   # official "home" stand
        mujoco.mj_forward(self.m, self.d)
        self.viewer = None
        if view:
            self.viewer = mujoco.viewer.launch_passive(self.m, self.d)

    def set_velocity(self, vx=0.0, vy=0.0, vyaw=0.0):
        self.vx, self.vy, self.vyaw = float(vx), float(vy), float(vyaw)

    def _desired_angles(self):
        moving = abs(self.vx) > 1e-3 or abs(self.vy) > 1e-3 or abs(self.vyaw) > 1e-3
        T_st = DUTY / GAIT_FREQ
        q = np.zeros(12)
        for k, lg in enumerate(LEGS):
            s = SIDE[lg]
            if not moving:
                px, py, pz = 0.0, s * L_OFF, -STAND_H
            else:
                rx, ry = self.foot_xy[lg]
                swx = _clip((-self.vx + self.vyaw * ry) * T_st, -SWEEP_MAX, SWEEP_MAX)
                swy = _clip((-self.vy - self.vyaw * rx) * T_st, -SWEEP_MAX, SWEEP_MAX)
                ph = (self.phase + PHASE_OFF[lg]) % 1.0
                if ph < DUTY:
                    t = ph / DUTY
                    dx, dy, dz = swx * (t - 0.5), swy * (t - 0.5), 0.0
                else:
                    t = (ph - DUTY) / (1 - DUTY)
                    dx, dy = swx * (0.5 - t), swy * (0.5 - t)
                    dz = STEP_HEIGHT * math.sin(math.pi * t)
                px, py, pz = dx, s * L_OFF + dy, -STAND_H + dz
            q[3 * k:3 * k + 3] = leg_ik(px, py, pz, s)
        return q, moving

    def step(self):
        q_des, moving = self._desired_angles()
        if moving:
            self.phase = (self.phase + GAIT_FREQ * self.dt) % 1.0
        tau = KP * (q_des - self.d.qpos[7:19]) - KD * self.d.qvel[6:18]
        self.d.ctrl[:] = np.clip(tau, -self.tau_lim, self.tau_lim)
        mujoco.mj_step(self.m, self.d)
        if self.viewer is not None:
            self.viewer.sync()

    def run(self, seconds):
        import time
        for _ in range(int(seconds / self.dt)):
            t0 = time.time()
            self.step()
            if self.viewer is not None:
                sl = self.dt - (time.time() - t0)
                if sl > 0:
                    time.sleep(sl)
                if not self.viewer.is_running():
                    break

    # -- head RealSense camera --------------------------------------------------
    def render_rgb(self, w=640, h=480):
        if self._rgb is None:
            self._rgb = mujoco.Renderer(self.m, h, w)
        self._rgb.update_scene(self.d, camera="head_cam")
        return self._rgb.render()

    def render_depth(self, w=640, h=480):
        if self._depth is None:
            self._depth = mujoco.Renderer(self.m, h, w)
            self._depth.enable_depth_rendering()
        self._depth.update_scene(self.d, camera="head_cam")
        return self._depth.render()

    def odom(self):
        return float(self.d.qpos[0]), float(self.d.qpos[1]), float(self.d.qpos[2])


def main():
    ap = argparse.ArgumentParser(description="Official Go2 velocity control + head RealSense (no RL/teleop).")
    ap.add_argument("--vx", type=float, default=0.0, help="forward vel m/s")
    ap.add_argument("--vy", type=float, default=0.0, help="left vel m/s")
    ap.add_argument("--vyaw", type=float, default=0.0, help="yaw rate rad/s")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--view", action="store_true", help="open the MuJoCo viewer")
    ap.add_argument("--headless", action="store_true", help="no window; print odometry")
    ap.add_argument("--snapshot", type=str, default=None, help="save head-cam RGB png at end")
    ap.add_argument("--depth-snapshot", type=str, default=None, help="save head-cam depth png at end")
    a = ap.parse_args()

    c = Go2Velocity(view=a.view and not a.headless)
    c.set_velocity(a.vx, a.vy, a.vyaw)
    x0, y0, _ = c.odom(); q0 = c.d.qpos[3:7].copy()
    c.run(a.seconds)
    x1, y1, z1 = c.odom()
    yaw = lambda q: math.atan2(2 * (q[0]*q[3] + q[1]*q[2]), 1 - 2 * (q[2]**2 + q[3]**2))
    print(f"cmd vx={a.vx} vy={a.vy} vyaw={a.vyaw} over {a.seconds}s -> "
          f"dx={x1-x0:+.3f} dy={y1-y0:+.3f} dyaw={yaw(c.d.qpos[3:7])-yaw(q0):+.3f} "
          f"z={z1:.3f} {'FELL' if z1 < 0.18 else 'OK'}")

    if a.snapshot:
        from PIL import Image
        Image.fromarray(c.render_rgb()).save(a.snapshot)
        print("saved RGB ->", a.snapshot)
    if a.depth_snapshot:
        from PIL import Image
        dep = c.render_depth(); dep = np.clip(dep, 0, 5.0)
        img = (255 * (1 - dep / 5.0)).astype(np.uint8)   # near=bright
        Image.fromarray(img).save(a.depth_snapshot)
        print("saved depth ->", a.depth_snapshot)


if __name__ == "__main__":
    main()
