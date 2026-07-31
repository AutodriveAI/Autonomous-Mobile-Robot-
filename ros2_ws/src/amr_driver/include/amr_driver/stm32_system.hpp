#pragma once

#include <regex>
#include <string>
#include <vector>

#include "hardware_interface/handle.hpp"
#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/macros.hpp"
#include "rclcpp_lifecycle/state.hpp"

namespace amr_driver
{

class STM32SystemHardware : public hardware_interface::SystemInterface
{
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(STM32SystemHardware)

  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareInfo & info) override;

  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;

  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override;

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

private:
  bool open_serial_port();
  void close_serial_port();
  bool configure_serial_port();
  void parse_received_bytes(const char * data, int length);
  void parse_line(const std::string & line);
  int rad_per_sec_to_ticks_per_sec(double rad_per_sec) const;
  double ticks_to_radians(long long ticks) const;
  double ticks_per_sec_to_rad_per_sec(int ticks_per_sec) const;

  std::string serial_port_{"/dev/ttyACM0"};
  int baud_rate_{115200};
  int ticks_per_revolution_{20};
  int max_ticks_per_second_{60};

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
