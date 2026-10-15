# AMR Operator GUI

Desktop controls for starting, monitoring, and debugging the physical robot.
The application is intended to run on the ROS 2 Humble development machine;
the robot processes continue to run on the ROS 2 Foxy Jetson.

## Current stage: complete bringup, localization, mapping, and Nav2 control

The application first verifies non-interactive SSH access. It then controls a
persistent `amr_bringup` and `amr_localisation` tmux sessions on the Jetson. It
provides:

- editable Jetson hostname/IP address, username, port, and optional key path;
- persistent settings in the desktop user's Qt settings directory;
- manual and automatic connection tests;
- automatic fallback from Wi-Fi SSH to the `nano_ethernet` cable alias;
- read-only two-sided LAN, gateway, internet-IP, and DNS diagnostics;
- a guarded, command-specific Jetson shutdown control;
- connection state and SSH diagnostic output;
- guarded start and graceful Ctrl-C stop controls for physical bringup;
- an optional hardware-start confirmation that can be disabled;
- collapsible connection and environment settings;
- one persistent local Humble RViz process using the unified real-robot view;
- one-click VS Code Remote-SSH access to the Jetson repository and Codex;
- remote map discovery and AMCL localization controls;
- guarded Slam Toolbox mapping and map saving into `amr_slam/maps`;
- a live end-to-end `map` to `base_link` Global TF indicator;
- guarded Nav2 lifecycle startup using `nav2_params_real.yaml`;
- a continuous `NavigateToPose` action-server readiness indicator;
- a state-aware System Health view for launch sessions, nodes, topics,
  lifecycle states, actions, message freshness, and TF;
- comment-preserving Nav2/twist-mux YAML tuning with ordered favorites, safe
  live updates, atomic saving, and process-aware restart controls;
- live and retained bringup/localization/Nav2/mapping logs in separate GUI tabs;
- persistent dark/light themes, semantic control colors, and adjustable log
  text size; and
- no password storage.

Physical bringup starts the motor driver, lidar, RGB camera, joystick, twist
mux, and LCD. Localization, mapping, and Nav2 remain separate actions so each
layer can be tested independently.

The application uses the system OpenSSH client. If authentication or host-key
verification needs interaction, configure it once in a normal terminal:

```bash
ssh jetson@ROBOT_IP
```

For passwordless access, copy the development machine's public key:

```bash
ssh-copy-id jetson@ROBOT_IP
```

## Build and run on the development machine

```bash
cd ~/Github/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/humble/setup.bash
sudo apt install python3-pyqt5 openssh-client ros-humble-rmw-cyclonedds-cpp
colcon build --symlink-install --packages-select amr_operator_gui
source install/amr_operator_gui/share/amr_operator_gui/package.bash
ros2 run amr_operator_gui operator_gui
```

Sourcing this package's `package.bash` directly avoids unrelated broken or
incomplete packages in the development workspace overlay.

The current Jetson address, `10.206.146.161`, is the default. Update the Host
field if that address changes, then select **Test SSH connection**. A successful
test prints the Jetson hostname and changes the status indicator to green.
This one startup check always runs. The **Check every 10 seconds** option controls
only subsequent periodic checks.

## Wi-Fi and direct-Ethernet SSH routes

The GUI treats the normal Jetson address as the preferred Wi-Fi route. The
**Fallback Ethernet SSH** section defaults to the SSH config alias found on the
development machine:

```sshconfig
Host nano_wifi
    HostName 10.206.146.161
    User jetson
    HostKeyAlias jetson-nano-lan

Host nano_ethernet
    HostName 10.42.0.129
    User jetson
    HostKeyAlias jetson-nano-lan
```

The Wi-Fi field defaults to `nano_wifi`. Older saved GUI settings that used the
cable address `10.42.0.129` as the main host are migrated to that Wi-Fi alias.

With **Automatically use Ethernet when Wi-Fi SSH fails** enabled, each connection
cycle tests Wi-Fi first and the cable route second. Wi-Fi remains active whenever
it is reachable. If it fails while `nano_ethernet` succeeds, all subsequent GUI
status checks and start/stop commands use Ethernet automatically. The two route
indicators show their individual state and the main indicator names the route
currently carrying commands.

The **Diagnose network** button is enabled whenever either SSH route works. It
runs read-only probes on the development machine and Jetson and places the full
evidence and summary in **Network Diagnosis**. The report includes:

- the route and source address used toward the other machine's Wi-Fi address;
- bidirectional Wi-Fi peer reachability;
- the selected internet/default route and gateway reachability;
- direct reachability of an internet IP address; and
- DNS resolution.

No interface, route, firewall, DNS, or NetworkManager setting is changed. Some
networks block ICMP ping, so interpret an internet-IP failure alongside DNS and
the printed routes rather than using that result alone.

## Safely shut down the Jetson

The red **Shutdown Jetson** button uses the currently active Wi-Fi or Ethernet
SSH route. It always asks for confirmation, reports any active robot sessions,
and invokes only `/bin/systemctl poweroff`. The button is disabled when neither
SSH route is connected. Losing SSH after an accepted request is expected.

The GUI deliberately cannot display, transmit, or store a sudo password. Add a
narrow passwordless rule once on the Jetson so only this power-off command is
authorized:

```bash
echo 'jetson ALL=(root) NOPASSWD: /bin/systemctl poweroff' | sudo tee /etc/sudoers.d/amr-operator-power
sudo chmod 440 /etc/sudoers.d/amr-operator-power
sudo visudo -cf /etc/sudoers.d/amr-operator-power
```

The final command must report that the file parsed successfully. If the Jetson
uses a different username, replace `jetson` in the rule. The shutdown action
uses `sudo -n`, so a missing or incorrect rule fails immediately instead of
leaving the application waiting for a password prompt.

## Appearance and log text

Use the button at the top-right of the window to switch between the dark and
light themes. The selected theme is restored the next time the GUI starts.

The following shortcuts change the text size in every log tab:

- `Ctrl++`: increase log text size;
- `Ctrl+-`: decrease log text size; and
- `Ctrl+0`: restore the default 10-point log text size.

The selected log size is also remembered across application restarts.

## System health supervision

The GUI starts one lightweight ROS health probe on the Jetson through the
currently active SSH route. Every two seconds it returns a compact structured
snapshot; it does not transfer images, scans, costmaps, or full logs. Select
**Show system health** or the **System Health** tab to inspect each check.

Checks are evaluated against the requested launch state:

- during startup, missing resources show as **Starting** for a bounded grace
  period;
- after an intentional GUI Stop, that subsystem shows as **Stopped** and its
  disappearing nodes/topics are not errors;
- a session that disappears without a Stop request is an **Error**;
- a session that remains after Stop becomes a possible-orphan **Warning**;
- loss of SSH makes remote health **Unknown**, rather than incorrectly marking
  every ROS component missing; and
- localization TF initially waits for the RViz initial pose, but losing that TF
  after it was healthy is an error.

Streaming health is based on last-arrival time for lightweight `/odom`, `/scan`,
`/joint_states`, and `/joy` messages. Camera health uses publisher metadata only,
so monitoring does not decode or copy RGB frames. Health changes are recorded in
the Connection log without recurring popup dialogs.

## Parameter tuning

Open **Parameter Tuning** to browse YAML files from the Jetson source tree at:

```text
ros2_ws/src/amr_navigation/config
```

Parameters remain in their original YAML order. Select the star in the first
column to retain an important parameter, then enable **Starred only** for a
short tuning view. Section rows such as **Path following (FollowPath)**,
**Goal checker**, and **Inflation layer** remain visible in that filtered view.
Stars are personal GUI preferences and do not modify the YAML file.

Editing a scalar creates a staged value. Orange value borders indicate unsaved
changes. Use **Save YAML** to commit every staged value atomically to the selected
file while preserving its existing comments. The save checks that the remote
file has not changed since it was loaded, validates the resulting YAML, and
keeps the previous file beside it as:

```text
<filename>.amr_operator_gui.bak
```

Closing the application with staged changes opens a **Save**, **Discard**, or
**Cancel** warning. **Save** completes the remote YAML write before allowing the
window to close. A live value that is discarded remains active in the running
node only until that process restarts.

The action in the final column depends on Foxy runtime support:

- **Send live** is shown only for parameters verified in the Foxy implementation
  to update their running component. The GUI asks for confirmation, sets the
  typed ROS parameter, and reads it back. The YAML still must be saved separately
  if the value should survive a restart.
- **↻ Restart Nav2** saves pending values with consent, cancels any active goal,
  gracefully stops the Nav2 tmux session, waits for cleanup, and starts it again.
- **↻ Restart bringup** is used for `twist_mux.yaml`. It is enabled only after
  Nav2, localization, and mapping are stopped, preserving dependency order.
- A simulation or otherwise externally owned YAML file can be edited and saved,
  but its external process must be restarted outside this physical-robot app.

The physical Nav2 launch reads `nav2_params_real.yaml` directly from the source
tree, so no `colcon build` is required after saving it. Restart Nav2 for values
that are not runtime-tunable.

### Install a desktop icon

After building and sourcing the package, run this once on the development
machine as the normal desktop user (do not use `sudo`):

```bash
ros2 run amr_operator_gui install_desktop_launcher
```

This installs **AMR Operator** in the application menu and creates
`~/Desktop/AMR Operator.desktop` when a Desktop directory exists. The generated
launcher sources ROS 2 Humble and this package before starting the GUI, so no
terminal is needed. If GNOME asks, right-click the desktop shortcut and select
**Allow Launching** once. Re-run the installer if the workspace is moved.

### Open the Jetson repository in VS Code

The **Open VS Code** button uses the current Jetson username, host, and remote
workspace fields to open the repository root through Remote-SSH. The development
machine must provide the `code` shell command and the Microsoft **Remote - SSH**
extension. Install the OpenAI Codex extension in that remote VS Code environment
and sign in once. This repository sets `chatgpt.openOnStartup`, so the Codex
sidebar focuses when the remote workspace finishes loading.

## Test physical bringup

Make sure `tmux` and Cyclone DDS are installed on the Jetson:

```bash
sudo apt install tmux ros-foxy-rmw-cyclonedds-cpp
```

Support the drive wheels or place the robot in a clear area, then select
**Start robot bringup**. The GUI asks for confirmation before starting hardware.
Uncheck **Confirm start** to suppress that dialog on later starts. With
**Auto-launch RViz** enabled, the unified saved RViz view opens after the remote
tmux session starts. RViz can also be launched and closed manually. The same
RViz process remains open as localization, mapping, or Nav2 starts; its already
configured displays begin updating when their topics and transforms appear.
The **Bringup Log** tab refreshes from:

```text
~/.local/state/amr_operator_gui/amr_bringup.log
```

Closing the GUI does not stop remote sessions, but it does close the local RViz
process. Reopening it reconnects to the same tmux sessions. **Stop bringup**
checks the actual Jetson sessions and automatically stops Nav2, then
localization or mapping, before sending Ctrl-C to physical bringup. One
confirmation covers the complete dependency-aware shutdown.
For an interactive terminal view, use:

```bash
ssh -t jetson@10.206.146.161 tmux attach-session -t amr_bringup
```

Detach without stopping it by pressing `Ctrl-B`, then `D`.

## Test localization

After physical bringup reports running:

1. Select one of the maps discovered from `amr_slam/maps`.
2. Select **Start localization**.
3. Inspect the **Localization Log** tab until AMCL and map_server are active.
4. Set the initial pose in RViz.
5. Confirm the `map → base_link available` indicator becomes green.

The localization log is retained on the Jetson at:

```text
~/.local/state/amr_operator_gui/amr_localisation.log
```

Localization must be stopped before the GUI enables physical bringup shutdown.
This preserves the dependency order and avoids leaving AMCL alive without the
driver, odometry, scan, and robot transforms.

The **Global TF: map → base_link** indicator is an end-to-end health check. It
turns green only when the transform from AMCL or Slam Toolbox (`map → odom`)
connects to wheel odometry (`odom → base_link`). This is the complete transform
RViz and Nav2 need to place the robot in the map.

**Auto-scroll logs** keeps the Bringup, Localization, and Mapping log tabs at
their newest output. Uncheck it when you want to scroll backward without the
next refresh pulling the view to the bottom.

## Create and save a new map

Physical bringup must be running and localization must be stopped:

1. Select **Start new map**. Slam Toolbox starts in the persistent
   `amr_mapping` tmux session.
2. If automatic RViz is enabled, the existing unified RViz process stays open
   and its `/map`, scan, robot, and TF displays update from Slam Toolbox.
3. Drive the robot through the environment with the joystick while monitoring
   the map and the **Mapping Log** tab.
4. Enter a map name such as `RestaurantFloor2`. Do not include `.yaml`.
5. Select **Save map** and confirm.
6. Select **Stop mapping** after the save completes.

Map names must start with a letter and may contain letters, numbers, underscores,
or hyphens. Existing `.yaml` or `.pgm` files are never overwritten; choose a new
name instead. The files are saved to:

```text
ros2_ws/src/amr_slam/maps/<MapName>.yaml
ros2_ws/src/amr_slam/maps/<MapName>.pgm
```

Mapping output is retained at:

```text
~/.local/state/amr_operator_gui/amr_mapping.log
```

Stopping mapping warns before discarding any unsaved map state. After mapping
stops, refresh the map list, select the new map, and start localization to test
it.

## Start and stop Nav2

The **Start Nav2** button remains disabled until all prerequisites are true:

- physical bringup is running;
- localization is running;
- mapping is stopped; and
- **Global TF: map → base_link** is green after setting the initial pose.

After selecting **Start Nav2**, wait for both indicators:

```text
Nav2 process running
NavigateToPose ready
```

The first confirms the remote tmux launch is alive. The second is a real ROS 2
action discovery probe and confirms `bt_navigator` finished lifecycle activation
and can accept goals. A running terminal alone does not imply Nav2 is ready.

The GUI always uses `amr_navigation/rviz/nav2_real_robot.rviz` as the unified
view. Starting Nav2 does not restart RViz; the costmaps, plan, and Nav2 panel
become live when their topics and action servers appear. Navigation goals can
then be sent from the Nav2 RViz panel.

Every Stop button may be used directly. **Stop localization** first stops Nav2
when it is active. **Stop bringup** performs the complete reverse dependency
order: Nav2, localization or mapping, then physical bringup. Each stage waits
up to 20 seconds for clean shutdown before continuing. A process launched
manually outside the app's known tmux sessions is reported instead of being
force-killed. Nav2 output is retained at:

```text
~/.local/state/amr_operator_gui/amr_nav2.log
```

The action readiness probe runs from `amr_operator_gui` on the Jetson. On a new
Jetson checkout, build this package once before using GUI-controlled Nav2:

```bash
cd ~/Autonomous_Mobile_Robot/Autonomous-Mobile-Robot-/ros2_ws
source /opt/ros/foxy/setup.bash
colcon build --symlink-install --packages-select amr_operator_gui
```

## Planned incremental rollout

1. SSH connectivity and settings (complete).
2. Persistent remote `tmux` session for physical robot bringup and live logs
   (complete).
3. Localization controls, map selection, local RViz, and TF readiness checks
   (complete).
4. Mapping controls and map-save workflow (complete).
5. Nav2 lifecycle controls and dependency-ordered startup/shutdown (current
   stage).

Each stage will remain independently testable before hardware-affecting controls
are added.
