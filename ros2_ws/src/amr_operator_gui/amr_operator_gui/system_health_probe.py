"""Low-overhead ROS graph, topic, lifecycle, action, and TF health probe."""

import json
import time

from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import JointState, Joy, LaserScan
from tf2_ros import Buffer, TransformException, TransformListener

from amr_operator_gui.health_model import HEALTH_MARKER


SNAPSHOT_INTERVAL_SECONDS = 2.0
FRESH_TOPICS = {
    "/odom": Odometry,
    "/scan": LaserScan,
    "/joint_states": JointState,
    "/joy": Joy,
}
OBSERVED_TOPICS = (
    "/odom",
    "/scan",
    "/joint_states",
    "/joy",
    "/robot_description",
    "/camera_rgb",
    "/camera_rgb/compressed",
    "/cmd_vel",
    "/cmd_vel_nav",
    "/map",
    "/amcl_pose",
    "/particlecloud",
    "/global_costmap/costmap",
    "/local_costmap/costmap",
    "/plan",
)
LIFECYCLE_NODES = (
    "map_server",
    "amcl",
    "controller_server",
    "planner_server",
    "recoveries_server",
    "bt_navigator",
    "waypoint_follower",
)
TRANSFORMS = {
    "odom_base": ("odom", "base_link", True),
    "map_odom": ("map", "odom", True),
    "map_base": ("map", "base_link", True),
    "base_lidar": ("base_link", "lidar_scan_link", False),
}


class SystemHealthProbe(Node):
    """Collect health without transferring bulk sensor messages off-robot."""

    def __init__(self) -> None:
        super().__init__("amr_system_health_probe")
        self._last_seen = {}
        self._subscriptions = []
        for topic_name, message_type in FRESH_TOPICS.items():
            subscription = self.create_subscription(
                message_type,
                topic_name,
                lambda _message, name=topic_name: self._record_message(name),
                qos_profile_sensor_data,
            )
            self._subscriptions.append(subscription)

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._navigate_client = ActionClient(
            self, NavigateToPose, "navigate_to_pose"
        )
        self._lifecycle_clients = {
            name: self.create_client(GetState, "/{}/get_state".format(name))
            for name in LIFECYCLE_NODES
        }

    def _record_message(self, topic_name: str) -> None:
        self._last_seen[topic_name] = time.monotonic()

    def _node_names(self):
        names = []
        for name, namespace in self.get_node_names_and_namespaces():
            namespace = namespace.rstrip("/")
            names.append("{}/{}".format(namespace, name) if namespace else "/" + name)
        return sorted(set(names))

    def _lifecycle_states(self):
        states = {}
        for name, client in self._lifecycle_clients.items():
            if not client.wait_for_service(timeout_sec=0.0):
                states[name] = "unavailable"
                continue
            future = client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(self, future, timeout_sec=0.08)
            result = future.result() if future.done() else None
            states[name] = (
                result.current_state.label.lower()
                if result is not None
                else "unresponsive"
            )
        return states

    def _transform(self, target: str, source: str, dynamic: bool):
        try:
            transform = self._tf_buffer.lookup_transform(
                target,
                source,
                Time(),
                timeout=Duration(seconds=0.02),
            )
        except TransformException:
            return {"available": False, "age": None}

        age = None
        if dynamic:
            stamp = transform.header.stamp
            stamp_ns = stamp.sec * 1000000000 + stamp.nanosec
            if stamp_ns:
                age = max(
                    0.0,
                    (self.get_clock().now().nanoseconds - stamp_ns) / 1e9,
                )
        return {
            "available": True,
            "age": round(age, 3) if age is not None else None,
        }

    def snapshot(self):
        """Return a compact JSON-serializable view of current ROS health."""
        now = time.monotonic()
        publishers = {
            topic: self.count_publishers(topic) for topic in OBSERVED_TOPICS
        }
        topic_age = {
            topic: (
                round(now - self._last_seen[topic], 3)
                if topic in self._last_seen
                else None
            )
            for topic in FRESH_TOPICS
        }
        transforms = {
            key: self._transform(target, source, dynamic)
            for key, (target, source, dynamic) in TRANSFORMS.items()
        }
        return {
            "version": 1,
            "timestamp": time.time(),
            "nodes": self._node_names(),
            "publishers": publishers,
            "topic_age": topic_age,
            "lifecycle": self._lifecycle_states(),
            "transforms": transforms,
            "actions": {
                "navigate_to_pose": self._navigate_client.server_is_ready()
            },
        }

    def close(self) -> None:
        """Release clients explicitly before node shutdown."""
        self._navigate_client.destroy()


def main() -> None:
    """Emit one machine-readable health snapshot every two seconds."""
    rclpy.init()
    node = SystemHealthProbe()
    next_snapshot = 0.0
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.2)
            now = time.monotonic()
            if now < next_snapshot:
                continue
            print(
                HEALTH_MARKER + json.dumps(node.snapshot(), separators=(",", ":")),
                flush=True,
            )
            next_snapshot = now + SNAPSHOT_INTERVAL_SECONDS
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
