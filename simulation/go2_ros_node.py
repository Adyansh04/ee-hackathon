#!/usr/bin/env python3
"""
ROS 2 node wrapping the MuJoCo Go2 velocity sim.

SUBSCRIBES:
    /cmd_vel            geometry_msgs/Twist     -> body velocity (linear.x, linear.y, angular.z)
PUBLISHES:
    /go2/odom           nav_msgs/Odometry       base pose + twist
    /go2/joint_states   sensor_msgs/JointState  12 leg joints
    /go2/camera/image_raw  sensor_msgs/Image    head RealSense RGB  (rgb8)
    /go2/camera/depth      sensor_msgs/Image    head RealSense depth (32FC1, metres)

So a teammate just publishes velocities and the simulated Go2 moves:
    ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
        "{linear: {x: 0.3, y: 0.0}, angular: {z: 0.4}}" -r 10

Run (needs ROS 2 sourced + the ROS-aware venv — see README):
    source /opt/ros/jazzy/setup.bash
    ./rosenv/bin/python go2_ros_node.py            # add --view for the MuJoCo window
"""
from __future__ import annotations
import argparse, time
import numpy as np
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, JointState

from go2_velocity import Go2Velocity, LEGS

SUBSTEPS = 4   # sim steps per loop iter (keeps real-time without 500 Hz Python overhead)
JOINT_NAMES = [f"{lg}_{j}_joint" for lg in LEGS for j in ("hip", "thigh", "calf")]


def _img_msg(stamp, frame, arr, encoding):
    m = Image()
    m.header.stamp = stamp; m.header.frame_id = frame
    m.height, m.width = int(arr.shape[0]), int(arr.shape[1])
    m.encoding = encoding; m.is_bigendian = 0
    m.step = int(arr.strides[0])
    m.data = arr.tobytes()
    return m


class Go2SimNode(Node):
    def __init__(self, view=False, camera=True, cam_w=320, cam_h=240):
        super().__init__("go2_sim")
        self.sim = Go2Velocity(view=view)
        self.camera = camera
        self.cam_w, self.cam_h = cam_w, cam_h
        self.create_subscription(Twist, "cmd_vel", self._on_cmd, 10)
        self.pub_odom = self.create_publisher(Odometry, "go2/odom", 10)
        self.pub_js   = self.create_publisher(JointState, "go2/joint_states", 10)
        self.pub_rgb  = self.create_publisher(Image, "go2/camera/image_raw", 2)
        self.pub_dep  = self.create_publisher(Image, "go2/camera/depth", 2)
        self.i = 0
        self.get_logger().info("go2_sim ready — publish geometry_msgs/Twist on /cmd_vel")

    def _on_cmd(self, msg: Twist):
        self.sim.set_velocity(msg.linear.x, msg.linear.y, msg.angular.z)

    def tick(self):
        for _ in range(SUBSTEPS):
            self.sim.step()
        self.i += 1
        if self.i % 3 == 0:          # ~40 Hz odom + joint states
            self._pub_state()
        if self.camera and self.i % 8 == 0:   # ~15 Hz camera
            self._pub_camera()

    def _pub_state(self):
        d = self.sim.d
        now = self.get_clock().now().to_msg()
        od = Odometry()
        od.header.stamp = now; od.header.frame_id = "odom"; od.child_frame_id = "base_link"
        od.pose.pose.position.x, od.pose.pose.position.y, od.pose.pose.position.z = map(float, d.qpos[0:3])
        w, x, y, z = (float(v) for v in d.qpos[3:7])          # MuJoCo (w,x,y,z)
        od.pose.pose.orientation.x = x; od.pose.pose.orientation.y = y
        od.pose.pose.orientation.z = z; od.pose.pose.orientation.w = w
        od.twist.twist.linear.x, od.twist.twist.linear.y, od.twist.twist.linear.z = map(float, d.qvel[0:3])
        od.twist.twist.angular.x, od.twist.twist.angular.y, od.twist.twist.angular.z = map(float, d.qvel[3:6])
        self.pub_odom.publish(od)
        js = JointState()
        js.header.stamp = now; js.name = JOINT_NAMES
        js.position = [float(v) for v in d.qpos[7:19]]
        js.velocity = [float(v) for v in d.qvel[6:18]]
        self.pub_js.publish(js)

    def _pub_camera(self):
        now = self.get_clock().now().to_msg()
        rgb = np.ascontiguousarray(self.sim.render_rgb(self.cam_w, self.cam_h))
        self.pub_rgb.publish(_img_msg(now, "head_cam", rgb, "rgb8"))
        dep = np.ascontiguousarray(self.sim.render_depth(self.cam_w, self.cam_h).astype(np.float32))
        self.pub_dep.publish(_img_msg(now, "head_cam", dep, "32FC1"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", action="store_true", help="open the MuJoCo viewer")
    ap.add_argument("--no-camera", action="store_true", help="skip camera publishing")
    ap.add_argument("--seconds", type=float, default=0.0, help="auto-stop after N s (0=forever)")
    a = ap.parse_args()
    rclpy.init()
    node = Go2SimNode(view=a.view, camera=not a.no_camera)
    dt = node.sim.dt * SUBSTEPS
    t_end = time.time() + a.seconds if a.seconds > 0 else None
    try:
        while rclpy.ok():
            t0 = time.time()
            rclpy.spin_once(node, timeout_sec=0.0)   # process incoming /cmd_vel
            node.tick()
            if t_end and time.time() > t_end:
                break
            sl = dt - (time.time() - t0)
            if sl > 0:
                time.sleep(sl)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
