"""Display Nav2 goal state on the physical robot's character LCD."""

from time import monotonic

from action_msgs.msg import GoalStatus
from action_msgs.msg import GoalStatusArray
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy
from rclpy.qos import HistoryPolicy
from rclpy.qos import QoSProfile
from rclpy.qos import ReliabilityPolicy

from amr_bringup.lcd_display import LcdDisplay


ACTIVE_STATUSES = (
    GoalStatus.STATUS_ACCEPTED,
    GoalStatus.STATUS_EXECUTING,
)
UNSUCCESSFUL_TERMINAL_STATUSES = (
    GoalStatus.STATUS_CANCELED,
    GoalStatus.STATUS_ABORTED,
)


class LcdStatusNode(Node):
    """Track NavigateToPose status transitions and render LCD screens."""

    def __init__(self):
        super().__init__('lcd_status')

        self.declare_parameter(
            'status_topic',
            '/navigate_to_pose/_action/status',
        )
        self.declare_parameter('goal_received_duration_s', 10.0)
        self.declare_parameter('goal_reached_duration_s', 20.0)

        status_topic = self.get_parameter('status_topic').value
        self._goal_received_duration_s = float(
            self.get_parameter('goal_received_duration_s').value
        )
        self._goal_reached_duration_s = float(
            self.get_parameter('goal_reached_duration_s').value
        )

        self._display = None
        self._goal_status_by_id = {}
        self._active_goal_id = None
        self._message_deadline = None

        try:
            self._display = LcdDisplay()
            self._show_idle()
        except ImportError:
            self.get_logger().error(
                'LCD disabled: install RPLCD with '
                '`sudo python3 -m pip install RPLCD`.'
            )
        except Exception as exc:
            # LCD failure must not stop the rest of physical robot bringup.
            self.get_logger().error(f'LCD initialization failed: {exc}')

        status_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._status_subscription = self.create_subscription(
            GoalStatusArray,
            status_topic,
            self._status_callback,
            status_qos,
        )
        self._deadline_timer = self.create_timer(0.2, self._check_deadline)

        self.get_logger().info(
            f'Watching Nav2 goal status on {status_topic}; '
            f'new-goal message duration is '
            f'{self._goal_received_duration_s:.1f} seconds.'
        )

    def close_display(self):
        """Release the LCD handle without clearing its final screen."""
        if self._display is None:
            return
        try:
            self._display.close()
        except Exception as exc:
            self.get_logger().warning(f'Could not close LCD cleanly: {exc}')
        self._display = None

    def _status_callback(self, message):
        statuses = sorted(
            message.status_list,
            key=lambda item: (
                item.goal_info.stamp.sec,
                item.goal_info.stamp.nanosec,
            ),
        )

        for goal_status in statuses:
            goal_id = bytes(goal_status.goal_info.goal_id.uuid)
            current_status = goal_status.status
            previous_status = self._goal_status_by_id.get(goal_id)

            if previous_status is None and current_status in ACTIVE_STATUSES:
                self._handle_new_goal(goal_id)
            elif previous_status != current_status:
                if (
                    current_status == GoalStatus.STATUS_SUCCEEDED
                    and goal_id == self._active_goal_id
                ):
                    self._handle_goal_succeeded(goal_id)
                elif (
                    current_status in UNSUCCESSFUL_TERMINAL_STATUSES
                    and goal_id == self._active_goal_id
                ):
                    self._handle_goal_ended_without_success(goal_id)

            self._goal_status_by_id[goal_id] = current_status

    def _handle_new_goal(self, goal_id):
        self._active_goal_id = goal_id
        self._show_lines(
            (
                'New goal received!',
                'Heading to',
                'destination...',
            )
        )
        self._set_deadline(self._goal_received_duration_s)
        self.get_logger().info(
            f'New navigation goal {self._short_goal_id(goal_id)} received.'
        )

    def _handle_goal_succeeded(self, goal_id):
        self._active_goal_id = None
        self._show_lines(
            (
                'Goal reached!',
                'Please collect',
                'your items! :)',
            )
        )
        self._set_deadline(self._goal_reached_duration_s)
        self.get_logger().info(
            f'Navigation goal {self._short_goal_id(goal_id)} reached.'
        )

    def _handle_goal_ended_without_success(self, goal_id):
        self._active_goal_id = None
        self._show_idle()
        self.get_logger().info(
            f'Navigation goal {self._short_goal_id(goal_id)} ended '
            'without success; restored idle display.'
        )

    def _set_deadline(self, duration_s):
        if duration_s <= 0.0:
            self._message_deadline = None
            return
        self._message_deadline = monotonic() + duration_s

    def _check_deadline(self):
        if self._message_deadline is None:
            return
        if monotonic() < self._message_deadline:
            return
        self._show_idle()

    def _show_lines(self, lines):
        self._message_deadline = None
        if self._display is None:
            return
        try:
            self._display.show_lines(lines)
        except Exception as exc:
            self.get_logger().error(f'LCD write failed: {exc}')

    def _show_idle(self):
        self._message_deadline = None
        if self._display is None:
            return
        try:
            self._display.show_idle_mark()
        except Exception as exc:
            self.get_logger().error(f'LCD idle-mark write failed: {exc}')

    @staticmethod
    def _short_goal_id(goal_id):
        return goal_id.hex()[:8]


def main(args=None):
    """Run the persistent LCD status node."""
    rclpy.init(args=args)
    node = LcdStatusNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close_display()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
