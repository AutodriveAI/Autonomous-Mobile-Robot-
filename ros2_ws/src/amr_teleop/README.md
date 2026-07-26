# AMR Teleoperation

`amr_teleop` provides safe keyboard control for the physical AMR. It publishes
`geometry_msgs/Twist` messages to `/cmd_vel`; `amr_driver` converts those
robot-level velocity commands into STM32 wheel-speed commands.

```text
keyboard → amr_teleop → /cmd_vel → amr_driver → STM32 → motors
```

## Run

Install the desktop keyboard-event dependency once:

```bash
sudo apt update
sudo apt install python3-pynput
```

Then start `amr_driver` first, and run this teleop package from an Ubuntu
desktop session (not a headless SSH-only terminal). `pynput` receives true
key-down and key-up events from the desktop.

Controls:

| Key | Action |
|---|---|
| Hold `w` | Forward; release to stop forward motion |
| Hold `s` | Reverse; release to stop reverse motion |
| Hold `a` / `d` | Rotate left / right; release to stop turning |
| `space` or `x` | Stop |
| `q` or Ctrl+C | Stop and quit |

Unlike the former terminal reader, this node receives both key-down and
key-up events. A held `w` remains forward for as long as it is physically held;
releasing it immediately removes forward motion. Holding `w+a` or `w+d`
commands a forward arc. `space` and `x` clear every active direction
immediately.

Because `pynput` listens to the desktop keyboard globally, keep this node
stopped while using other applications. While it is running, a `w`, `a`, `s`,
or `d` press in another application is still a robot command.

## Parameters

| Parameter | Default | Meaning |
|---|---:|---|
| `cmd_vel_topic` | `cmd_vel` | ROS topic on which this node publishes `geometry_msgs/Twist`. This must match the driver subscription. |
| `linear_speed_mps` | `0.10` | Forward/reverse speed used by `w` and `s`, in metres per second. |
| `angular_speed_radps` | `0.80` | Turn speed used by `a` and `d`, in radians per second. |
| `publish_rate_hz` | `20.0` | How often the current command is published while valid. It also refreshes the driver and STM32 watchdog chain. |

Override speed values when launching, for example:

```bash
ros2 run amr_teleop keyboard_teleop --ros-args \
  -p linear_speed_mps:=0.05 -p angular_speed_radps:=0.4
```

For example, a lifted-wheel test that requests `0.3 m/s` is:

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run amr_teleop keyboard_teleop --ros-args \
  -p linear_speed_mps:=0.3
```
