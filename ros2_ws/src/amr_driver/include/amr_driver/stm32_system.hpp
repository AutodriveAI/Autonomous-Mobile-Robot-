#pragma once

#include <regex>
#include <string>
#include <vector>

#include "hardware_interface/handle.hpp"
#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
#include "hardware_interface/base_interface.hpp"
#else
#include "rclcpp/macros.hpp"
#endif
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/state.hpp"

namespace amr_driver
{

class STM32SystemHardware :
#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
  public hardware_interface::BaseInterface<hardware_interface::SystemInterface>
#else
  public hardware_interface::SystemInterface
#endif
{
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(STM32SystemHardware)

#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
  hardware_interface::return_type configure(
    const hardware_interface::HardwareInfo & info) override;
#else
  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareInfo & info) override;
#endif

  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;

  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override;

#ifdef AMR_DRIVER_ROS2_CONTROL_FOXY
  hardware_interface::return_type start() override;

  hardware_interface::return_type stop() override;

  hardware_interface::return_type read() override;

  hardware_interface::return_type write() override;
#else
  hardware_interface::CallbackReturn on_activate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_deactivate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::return_type read(
    const rclcpp::Time & time,
    const rclcpp::Duration & period) override;

  hardware_interface::return_type write(
    const rclcpp::Time & time,
    const rclcpp::Duration & period) override;
#endif

private:
  bool open_serial_port();
  void close_serial_port();
  bool configure_serial_port();
  void parse_received_bytes(const char * data, int length);
  void parse_line(const std::string & line);
  int rad_per_sec_to_ticks_per_sec(double rad_per_sec) const;
  double ticks_to_radians(long long ticks) const;
  double ticks_per_sec_to_rad_per_sec(int ticks_per_sec) const;

  std::string serial_port_{"/dev/stm32"};
  int baud_rate_{115200};
  int ticks_per_revolution_{20};
  int max_ticks_per_second_{200};

  int serial_fd_{-1};
  std::string receive_buffer_;
  std::regex telemetry_regex_;

  double left_command_rad_per_sec_{0.0};
  double right_command_rad_per_sec_{0.0};

  double left_position_rad_{0.0};
  double right_position_rad_{0.0};
  double left_velocity_rad_per_sec_{0.0};
  double right_velocity_rad_per_sec_{0.0};

  int last_left_command_ticks_per_sec_{0};
  int last_right_command_ticks_per_sec_{0};
};

}  // namespace amr_driver
