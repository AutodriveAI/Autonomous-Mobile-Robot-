"""Display the newest JPEG camera frame received over ROS 2."""

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy
from rclpy.qos import HistoryPolicy
from rclpy.qos import QoSProfile
from rclpy.qos import ReliabilityPolicy
from sensor_msgs.msg import CompressedImage


class RemoteRgbViewer(Node):
    """Best-effort, one-frame-queue viewer for a remote compressed stream."""

    def __init__(self):
        super().__init__('remote_rgb_viewer')

        self.declare_parameter('topic', '/camera_rgb/compressed')
        self.declare_parameter('window_name', 'AMR camera')
        topic = self.get_parameter('topic').value
        self._window_name = self.get_parameter('window_name').value
        self._latest_frame = None
        self.stop_requested = False

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._subscription = self.create_subscription(
            CompressedImage,
            topic,
            self._image_callback,
            qos,
        )
        self._display_timer = self.create_timer(0.01, self._display_latest)
        self.get_logger().info(
            'Viewing newest frame from %s (best effort, queue depth 1). '
            'Press Esc or q to close.' % topic
        )

    def _image_callback(self, message):
        encoded = np.frombuffer(message.data, dtype=np.uint8)
        frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if frame is None:
            self.get_logger().warning(
                'Received a JPEG frame that OpenCV could not decode.'
            )
            return
        self._latest_frame = frame

    def _display_latest(self):
        if self._latest_frame is None:
            return

        cv2.imshow(self._window_name, self._latest_frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q')):
            self.stop_requested = True


def main(args=None):
    rclpy.init(args=args)
    node = RemoteRgbViewer()
    try:
        while rclpy.ok() and not node.stop_requested:
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        cv2.destroyAllWindows()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
