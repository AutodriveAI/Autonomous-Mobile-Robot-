"""Small ROS 2 probe that reports NavigateToPose action availability."""

import time

from nav2_msgs.action import NavigateToPose
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node


READY_MARKER = "__AMR_NAV2_ACTION_READY__"
WAITING_MARKER = "__AMR_NAV2_ACTION_WAITING__"


def main() -> None:
    """Continuously report whether bt_navigator offers NavigateToPose."""
    rclpy.init()
    node = Node("amr_nav2_health_probe")
    client = ActionClient(node, NavigateToPose, "navigate_to_pose")
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.2)
            marker = READY_MARKER if client.server_is_ready() else WAITING_MARKER
            print(marker, flush=True)
            time.sleep(0.8)
    except KeyboardInterrupt:
        pass
    finally:
        client.destroy()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
