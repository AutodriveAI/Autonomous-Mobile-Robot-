#include "amr_driver/stm32_system.hpp"

// This file implements the real-robot "hardware plugin" for ros2_control.
//
// Think of ros2_control as having three layers:
//
//   1. A controller, for example diff_drive_controller.
//      It understands robot-level commands like /cmd_vel and converts them into
//      left/right wheel joint commands.
//
//   2. A hardware interface, this file.
//      It exposes wheel joints to ros2_control and translates between ROS units
//      and our STM32 serial protocol.
//
//   3. The actual hardware, our STM32 firmware.
//      It receives commands such as:
//
//        V,<left_ticks_per_second>,<right_ticks_per_second>
//
//      and sends telemetry such as:
//
//        LTicks:... LPWM:... LCTPS:... RTicks:... RPWM:... RCTPS:...
//
// The important idea: this file does NOT implement PID. It only converts and
// transports commands/feedback. The STM32 firmware still owns the motor PID.

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstring>
#include <limits>
#include <sstream>
#include <stdexcept>

#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "rclcpp/rclcpp.hpp"

namespace amr_driver
{
namespace
{

constexpr const char * LOGGER_NAME = "amr_driver.STM32SystemHardware";

#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
using lifecycle_return_type = hardware_interface::return_type;
constexpr auto LIFECYCLE_SUCCESS = hardware_interface::return_type::OK;
constexpr auto LIFECYCLE_ERROR = hardware_interface::return_type::ERROR;
#else
using lifecycle_return_type = hardware_interface::CallbackReturn;
constexpr auto LIFECYCLE_SUCCESS = hardware_interface::CallbackReturn::SUCCESS;
constexpr auto LIFECYCLE_ERROR = hardware_interface::CallbackReturn::ERROR;
#endif

// Read an integer parameter from the <hardware> section of ros2_control.xacro.
//
// Example in xacro:
//
//   <param name="baud_rate">115200</param>
//
// ros2_control loads those parameters into HardwareInfo::hardware_parameters.
// If the parameter is missing, we keep a safe default from the class member.
int get_int_parameter(
  const hardware_interface::HardwareInfo & info,
  const std::string & name,
  int default_value)
{
  const auto iter = info.hardware_parameters.find(name);
  return iter == info.hardware_parameters.end() ? default_value : std::stoi(iter->second);
}

// Same idea as get_int_parameter(), but for string parameters such as:
//
//   <param name="serial_port">/dev/ttyACM0</param>
std::string get_string_parameter(
  const hardware_interface::HardwareInfo & info,
  const std::string & name,
  const std::string & default_value)
{
  const auto iter = info.hardware_parameters.find(name);
  return iter == info.hardware_parameters.end() ? default_value : iter->second;
}

// Linux serial ports do not accept a plain integer baud rate directly in
// cfsetospeed()/cfsetispeed(). They want constants like B115200.
//
// This helper maps our human-readable baud_rate parameter to the termios
// constant expected by the operating system.
speed_t baud_to_termios_constant(int baud_rate)
{
  switch (baud_rate) {
    case 9600: return B9600;
    case 19200: return B19200;
    case 38400: return B38400;
    case 57600: return B57600;
    case 115200: return B115200;
    default:
      throw std::runtime_error("Unsupported baud_rate. Supported: 9600, 19200, 38400, 57600, 115200");
  }
}

}  // namespace

#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
lifecycle_return_type STM32SystemHardware::configure(
#else
lifecycle_return_type STM32SystemHardware::on_init(
#endif
  const hardware_interface::HardwareInfo & info)
{
  // Let the base ros2_control SystemInterface parse and store the URDF
  // hardware information first. This fills info_, including the joint names,
  // command interfaces, state interfaces, and hardware parameters.
#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
  if (hardware_interface::BaseInterface<hardware_interface::SystemInterface>::configure(info) !=
    hardware_interface::return_type::OK)
#else
  if (hardware_interface::SystemInterface::on_init(info) !=
    hardware_interface::CallbackReturn::SUCCESS)
#endif
  {
    return LIFECYCLE_ERROR;
  }

  // Our AMR base has exactly two controllable joints:
  //
  //   - left_wheel_joint
  //   - right_wheel_joint
  //
  // If the URDF/xacro declares anything else for this hardware block, the
  // controller and hardware interface would disagree about what is being driven.
  if (info_.joints.size() != 2) {
    RCLCPP_ERROR(
      rclcpp::get_logger(LOGGER_NAME),
      "Expected exactly 2 joints, got %zu",
      info_.joints.size());
    return LIFECYCLE_ERROR;
  }

  // Validate the interface shape of each wheel joint.
  //
  // For diff_drive_controller, each wheel needs:
  //
  //   command interface:
  //     velocity
  //
  //   state interfaces:
  //     position
  //     velocity
  //
  // "Velocity command" means the controller will ask each wheel to spin at some
  // angular speed in rad/s. "Position state" and "velocity state" are feedback
  // from the encoder, also in ROS joint units.
  for (const auto & joint : info_.joints) {
    if (joint.command_interfaces.size() != 1 ||
      joint.command_interfaces[0].name != hardware_interface::HW_IF_VELOCITY)
    {
      RCLCPP_ERROR(
        rclcpp::get_logger(LOGGER_NAME),
        "Joint '%s' must have exactly one velocity command_interface",
        joint.name.c_str());
      return LIFECYCLE_ERROR;
    }

    if (joint.state_interfaces.size() != 2) {
      RCLCPP_ERROR(
        rclcpp::get_logger(LOGGER_NAME),
        "Joint '%s' must have position and velocity state_interfaces",
        joint.name.c_str());
      return LIFECYCLE_ERROR;
    }
  }

  // Pull real hardware settings from ros2_control.xacro.
  //
  // These are deliberately parameters, not hardcoded constants, because the
  // serial port or encoder resolution may change between computers/robots.
  serial_port_ = get_string_parameter(info_, "serial_port", serial_port_);
  baud_rate_ = get_int_parameter(info_, "baud_rate", baud_rate_);
  ticks_per_revolution_ = get_int_parameter(info_, "ticks_per_revolution", ticks_per_revolution_);
  max_ticks_per_second_ = get_int_parameter(info_, "max_ticks_per_second", max_ticks_per_second_);

  // A zero or negative encoder resolution would make ticks-to-radians math
  // impossible, so fail early instead of producing nonsense odometry.
  if (ticks_per_revolution_ <= 0) {
    RCLCPP_ERROR(rclcpp::get_logger(LOGGER_NAME), "ticks_per_revolution must be positive");
    return LIFECYCLE_ERROR;
  }

  // Regex for parsing the current STM32 telemetry line.
  //
  // Example accepted line:
  //
  //   LTicks:123 LPWM:210 LCTPS:45 RTicks:120 RPWM:205 RCTPS:44
  //
  // Captured groups:
  //   1 = left total ticks
  //   2 = left PWM       currently ignored by ros2_control
  //   3 = left CTPS      current ticks per second
  //   4 = right total ticks
  //   5 = right PWM      currently ignored by ros2_control
  //   6 = right CTPS     current ticks per second
  telemetry_regex_ = std::regex(
    R"(LTicks:(\d+)\s+LPWM:(-?\d+)\s+LCTPS:(-?\d+)\s+RTicks:(\d+)\s+RPWM:(-?\d+)\s+RCTPS:(-?\d+))");

  RCLCPP_INFO(
    rclcpp::get_logger(LOGGER_NAME),
    "Configured STM32 hardware: port=%s baud=%d ticks/rev=%d max_ticks/s=%d",
    serial_port_.c_str(), baud_rate_, ticks_per_revolution_, max_ticks_per_second_);

  return LIFECYCLE_SUCCESS;
}

std::vector<hardware_interface::StateInterface>
STM32SystemHardware::export_state_interfaces()
{
  // These variables are how ros2_control reads feedback from this plugin.
  //
  // We give ros2_control pointers to our member variables. Later, every time
  // read() parses STM32 telemetry, it updates these variables. The controller
  // then sees the new wheel positions/velocities through these exported state
  // interfaces.
  std::vector<hardware_interface::StateInterface> state_interfaces;
  state_interfaces.emplace_back(
    info_.joints[0].name, hardware_interface::HW_IF_POSITION, &left_position_rad_);
  state_interfaces.emplace_back(
    info_.joints[0].name, hardware_interface::HW_IF_VELOCITY, &left_velocity_rad_per_sec_);
  state_interfaces.emplace_back(
    info_.joints[1].name, hardware_interface::HW_IF_POSITION, &right_position_rad_);
  state_interfaces.emplace_back(
    info_.joints[1].name, hardware_interface::HW_IF_VELOCITY, &right_velocity_rad_per_sec_);
  return state_interfaces;
}

std::vector<hardware_interface::CommandInterface>
STM32SystemHardware::export_command_interfaces()
{
  // These variables are how ros2_control writes commands into this plugin.
  //
  // diff_drive_controller calculates left/right wheel angular velocities in
  // rad/s and writes those values into these member variables. Later, write()
  // converts them to encoder ticks per second and sends them to the STM32.
  std::vector<hardware_interface::CommandInterface> command_interfaces;
  command_interfaces.emplace_back(
    info_.joints[0].name, hardware_interface::HW_IF_VELOCITY, &left_command_rad_per_sec_);
  command_interfaces.emplace_back(
    info_.joints[1].name, hardware_interface::HW_IF_VELOCITY, &right_command_rad_per_sec_);
  return command_interfaces;
}

#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
lifecycle_return_type STM32SystemHardware::start()
#else
lifecycle_return_type STM32SystemHardware::on_activate(
  const rclcpp_lifecycle::State &)
#endif
{
  // Reset command and feedback memory whenever the hardware interface is
  // activated. Activation normally happens when controller_manager starts this
  // hardware plugin.
  //
  // We start from zero so the robot does not inherit stale commands or stale
  // encoder states from a previous process.
  left_command_rad_per_sec_ = 0.0;
  right_command_rad_per_sec_ = 0.0;
  left_position_rad_ = 0.0;
  right_position_rad_ = 0.0;
  left_velocity_rad_per_sec_ = 0.0;
  right_velocity_rad_per_sec_ = 0.0;
  last_left_command_ticks_per_sec_ = std::numeric_limits<int>::min();
  last_right_command_ticks_per_sec_ = std::numeric_limits<int>::min();
  receive_buffer_.clear();

  // The serial port is opened only during activation, not during construction.
  // That matches ros2_control lifecycle behavior and lets configuration fail
  // cleanly before touching hardware.
  if (!open_serial_port()) {
    return LIFECYCLE_ERROR;
  }

  RCLCPP_INFO(
    rclcpp::get_logger(LOGGER_NAME),
    "Activated STM32 hardware interface on %s @ %d baud",
    serial_port_.c_str(), baud_rate_);
  return LIFECYCLE_SUCCESS;
}

#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
lifecycle_return_type STM32SystemHardware::stop()
#else
lifecycle_return_type STM32SystemHardware::on_deactivate(
  const rclcpp_lifecycle::State &)
#endif
{
  // On shutdown/deactivation, command both wheels to zero before closing the
  // port. This mirrors the safety idea used in the STM32 firmware: if the ROS
  // side stops, the robot should not keep driving.
  left_command_rad_per_sec_ = 0.0;
  right_command_rad_per_sec_ = 0.0;
#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
  write();
#else
  write(rclcpp::Time{}, rclcpp::Duration::from_seconds(0.0));
#endif
  close_serial_port();
  return LIFECYCLE_SUCCESS;
}

#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
hardware_interface::return_type STM32SystemHardware::read()
#else
hardware_interface::return_type STM32SystemHardware::read(
  const rclcpp::Time &,
  const rclcpp::Duration &)
#endif
{
  // ros2_control calls read() periodically.
  //
  // For our hardware, "read" means:
  //
  //   1. Pull any available bytes from the serial port.
  //   2. Split those bytes into complete newline-terminated text lines.
  //   3. Parse encoder telemetry.
  //   4. Update wheel position/velocity state variables.
  //
  // The serial port is non-blocking, so this function does not wait forever.
  // If there is no new data, it simply returns OK and lets the controller loop
  // continue.
  if (serial_fd_ < 0) {
    return hardware_interface::return_type::ERROR;
  }

  char buffer[256];
  while (true) {
    const int bytes_read = ::read(serial_fd_, buffer, sizeof(buffer));
    if (bytes_read > 0) {
      // We may receive half a line, one full line, or several lines at once.
      // parse_received_bytes() handles that by accumulating text until '\n'.
      parse_received_bytes(buffer, bytes_read);
      continue;
    }

    // With O_NONBLOCK, Linux reports "nothing available right now" as EAGAIN
    // or EWOULDBLOCK. That is not an error for us.
    if (bytes_read == 0 || errno == EAGAIN || errno == EWOULDBLOCK) {
      return hardware_interface::return_type::OK;
    }

    RCLCPP_ERROR(rclcpp::get_logger(LOGGER_NAME), "Serial read failed: %s", std::strerror(errno));
    return hardware_interface::return_type::ERROR;
  }
}

#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
hardware_interface::return_type STM32SystemHardware::write()
#else
hardware_interface::return_type STM32SystemHardware::write(
  const rclcpp::Time &,
  const rclcpp::Duration &)
#endif
{
  // ros2_control calls write() periodically after controllers update commands.
  //
  // For our hardware, "write" means:
  //
  //   1. Read desired wheel angular speeds from left_command_rad_per_sec_ and
  //      right_command_rad_per_sec_.
  //   2. Convert rad/s into encoder ticks/s.
  //   3. Send the STM32 velocity command:
  //
  //        V,<left_ticks_per_second>,<right_ticks_per_second>\n
  //
  // The STM32 firmware receives this V command and runs its local wheel-speed
  // PID. Again: no PID is implemented here.
  if (serial_fd_ < 0) {
    return hardware_interface::return_type::ERROR;
  }

  const int left_ticks = rad_per_sec_to_ticks_per_sec(left_command_rad_per_sec_);
  const int right_ticks = rad_per_sec_to_ticks_per_sec(right_command_rad_per_sec_);

  // Do not spam identical serial commands.
  //
  // If the command has not changed since the previous write(), skipping it
  // reduces USB serial traffic. The STM32 already has its own command timeout,
  // so if we later find this causes timeout trouble, we can change this to
  // resend at a slow keepalive rate. For now this keeps the link cleaner.
  if (left_ticks == last_left_command_ticks_per_sec_ &&
    right_ticks == last_right_command_ticks_per_sec_)
  {
    return hardware_interface::return_type::OK;
  }

  std::ostringstream command;
  command << "V," << left_ticks << "," << right_ticks << "\n";
  const std::string command_string = command.str();

  // Low-level POSIX write to the USB serial device, for example /dev/ttyACM0.
  const ssize_t bytes_written = ::write(serial_fd_, command_string.c_str(), command_string.size());
  if (bytes_written < 0) {
    RCLCPP_ERROR(rclcpp::get_logger(LOGGER_NAME), "Serial write failed: %s", std::strerror(errno));
    return hardware_interface::return_type::ERROR;
  }

  last_left_command_ticks_per_sec_ = left_ticks;
  last_right_command_ticks_per_sec_ = right_ticks;
  return hardware_interface::return_type::OK;
}

bool STM32SystemHardware::open_serial_port()
{
  // O_RDWR:     open for reading and writing.
  // O_NOCTTY:  do not make this serial device the controlling terminal for
  //            this process. We want it as a device, not as our shell.
  // O_NONBLOCK: read() returns immediately when no bytes are available.
  serial_fd_ = ::open(serial_port_.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (serial_fd_ < 0) {
    RCLCPP_ERROR(
      rclcpp::get_logger(LOGGER_NAME),
      "Failed to open serial port '%s': %s",
      serial_port_.c_str(), std::strerror(errno));
    return false;
  }

  if (!configure_serial_port()) {
    close_serial_port();
    return false;
  }

  return true;
}

void STM32SystemHardware::close_serial_port()
{
  // File descriptors are small integer handles owned by the operating system.
  // Closing them when done releases the serial device cleanly.
  if (serial_fd_ >= 0) {
    ::close(serial_fd_);
    serial_fd_ = -1;
  }
}

bool STM32SystemHardware::configure_serial_port()
{
  // termios is the Linux/POSIX API for serial-port configuration.
  // It controls baud rate, number of data bits, parity, stop bits, flow control,
  // line buffering, echo, and blocking behavior.
  termios tty {};
  if (tcgetattr(serial_fd_, &tty) != 0) {
    RCLCPP_ERROR(rclcpp::get_logger(LOGGER_NAME), "tcgetattr failed: %s", std::strerror(errno));
    return false;
  }

  try {
    // Apply the same baud rate in both directions:
    //
    //   output speed: PC -> STM32
    //   input speed:  STM32 -> PC
    const speed_t speed = baud_to_termios_constant(baud_rate_);
    cfsetospeed(&tty, speed);
    cfsetispeed(&tty, speed);
  } catch (const std::exception & error) {
    RCLCPP_ERROR(rclcpp::get_logger(LOGGER_NAME), "%s", error.what());
    return false;
  }

  // CLOCAL: ignore modem-control lines. USB serial does not need old-school
  //         modem carrier-detect behavior.
  //
  // CREAD: enable receiving bytes.
  tty.c_cflag |= static_cast<tcflag_t>(CLOCAL | CREAD);

  // Clear the character-size field, then select 8 data bits.
  tty.c_cflag &= static_cast<tcflag_t>(~CSIZE);
  tty.c_cflag |= CS8;

  // Disable parity bit: 8N1 serial format.
  // 8N1 = 8 data bits, No parity, 1 stop bit.
  tty.c_cflag &= static_cast<tcflag_t>(~PARENB);

  // Disable two-stop-bit mode, leaving one stop bit: 8N1.
  tty.c_cflag &= static_cast<tcflag_t>(~CSTOPB);

  // Disable RTS/CTS hardware flow control. The STM32 UART protocol here does
  // not use extra flow-control wires.
  tty.c_cflag &= static_cast<tcflag_t>(~CRTSCTS);

  // Disable canonical terminal behavior.
  //
  // Normally a terminal can buffer by lines, echo characters, and handle Ctrl+C.
  // For a binary/text device protocol, we want raw bytes instead.
  tty.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO | ECHOE | ISIG));

  // Disable software flow control characters such as Ctrl+S / Ctrl+Q.
  tty.c_iflag &= static_cast<tcflag_t>(~(IXON | IXOFF | IXANY));

  // Do not translate carriage returns/newlines. The STM32 sends explicit text
  // lines, and parse_received_bytes() handles '\n' and optional '\r'.
  tty.c_iflag &= static_cast<tcflag_t>(~(INLCR | ICRNL | IGNCR));

  // Disable output post-processing. Bytes we write should go out unchanged.
  tty.c_oflag &= static_cast<tcflag_t>(~OPOST);

  // VMIN=0 and VTIME=0 make reads return immediately. Together with O_NONBLOCK,
  // this keeps ros2_control's update loop from freezing if the STM32 is quiet.
  tty.c_cc[VMIN] = 0;
  tty.c_cc[VTIME] = 0;

  if (tcsetattr(serial_fd_, TCSANOW, &tty) != 0) {
    RCLCPP_ERROR(rclcpp::get_logger(LOGGER_NAME), "tcsetattr failed: %s", std::strerror(errno));
    return false;
  }

  // Drop stale bytes that may already be sitting in the USB serial buffers.
  // This avoids parsing an old partial line as fresh telemetry.
  tcflush(serial_fd_, TCIOFLUSH);
  return true;
}

void STM32SystemHardware::parse_received_bytes(const char * data, int length)
{
  // Serial is a byte stream, not a packet stream.
  //
  // That means one read() call might return:
  //
  //   - half of a telemetry line
  //   - exactly one line
  //   - multiple lines stuck together
  //
  // So we append bytes into receive_buffer_ and only parse once a newline
  // appears.
  receive_buffer_.append(data, static_cast<std::size_t>(length));

  std::size_t newline_position = std::string::npos;
  while ((newline_position = receive_buffer_.find('\n')) != std::string::npos) {
    // Extract one complete line, not including the newline character.
    std::string line = receive_buffer_.substr(0, newline_position);

    // Remove that complete line from the buffer. Any bytes after the newline
    // stay in receive_buffer_ for the next loop iteration.
    receive_buffer_.erase(0, newline_position + 1);

    // Many serial tools use CRLF line endings: "\r\n".
    // We split on '\n', then remove the optional '\r'.
    if (!line.empty() && line.back() == '\r') {
      line.pop_back();
    }
    parse_line(line);
  }

  // Safety guard: if the STM32 sends garbage without newlines, the receive
  // buffer could otherwise grow forever. Clearing it loses one bad partial
  // message, but keeps the ROS node alive.
  if (receive_buffer_.size() > 1024) {
    receive_buffer_.clear();
  }
}

void STM32SystemHardware::parse_line(const std::string & line)
{
  // Ignore any line that does not match our telemetry format. This is useful
  // because the STM32 may also print OK messages, debug text, or startup text.
  std::smatch match;
  if (!std::regex_search(line, match, telemetry_regex_)) {
    return;
  }

  const long long left_ticks = std::stoll(match[1].str());
  const int left_ticks_per_second = std::stoi(match[3].str());
  const long long right_ticks = std::stoll(match[4].str());
  const int right_ticks_per_second = std::stoi(match[6].str());

  // Convert encoder units into ROS joint units:
  //
  //   total ticks       -> wheel angle in radians
  //   ticks per second  -> wheel angular velocity in radians/second
  //
  // diff_drive_controller uses these states for odometry and feedback.
  left_position_rad_ = ticks_to_radians(left_ticks);
  right_position_rad_ = ticks_to_radians(right_ticks);
  left_velocity_rad_per_sec_ = ticks_per_sec_to_rad_per_sec(left_ticks_per_second);
  right_velocity_rad_per_sec_ = ticks_per_sec_to_rad_per_sec(right_ticks_per_second);
}

int STM32SystemHardware::rad_per_sec_to_ticks_per_sec(double rad_per_sec) const
{
  // Convert from ROS wheel angular velocity to the STM32 velocity command unit.
  //
  // One full wheel revolution is:
  //
  //   2*pi radians
  //
  // Our encoder reports:
  //
  //   ticks_per_revolution_ ticks / revolution
  //
  // Therefore:
  //
  //   ticks/s = rad/s * ticks/rev / (2*pi rad/rev)
  const double ticks_per_second =
    rad_per_sec * static_cast<double>(ticks_per_revolution_) / (2.0 * M_PI);

  // Clamp before sending to STM32 so a bad ROS command cannot request an
  // absurd wheel speed. The STM32 should still clamp too; this is an extra
  // safety layer on the PC side.
  const double clamped = std::clamp(
    ticks_per_second,
    -static_cast<double>(max_ticks_per_second_),
    static_cast<double>(max_ticks_per_second_));
  return static_cast<int>(std::lround(clamped));
}

double STM32SystemHardware::ticks_to_radians(long long ticks) const
{
  // Convert absolute encoder tick count into wheel angle.
  //
  // Example with 20 ticks/rev:
  //
  //   20 ticks -> 2*pi radians
  //   10 ticks -> pi radians
  return static_cast<double>(ticks) * 2.0 * M_PI /
         static_cast<double>(ticks_per_revolution_);
}

double STM32SystemHardware::ticks_per_sec_to_rad_per_sec(int ticks_per_sec) const
{
  // Convert measured encoder rate into ROS angular velocity.
  //
  // Example with 20 ticks/rev:
  //
  //   20 ticks/s -> 2*pi rad/s -> 1 wheel rev/s
  return static_cast<double>(ticks_per_sec) * 2.0 * M_PI /
         static_cast<double>(ticks_per_revolution_);
}

}  // namespace amr_driver

PLUGINLIB_EXPORT_CLASS(
  amr_driver::STM32SystemHardware,
  hardware_interface::SystemInterface)

// This macro makes the class discoverable by pluginlib.
//
// ros2_control does not directly instantiate STM32SystemHardware by calling a
// constructor in our code. Instead, it reads this plugin name from the URDF:
//
//   amr_driver/STM32SystemHardware
//
// Then pluginlib loads the shared library and creates this class dynamically.
