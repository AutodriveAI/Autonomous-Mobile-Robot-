cmake_minimum_required(VERSION 3.8)
project(amr_driver)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(hardware_interface REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)

add_library(amr_driver_stm32_hardware SHARED
  src/stm32_system.cpp
)

target_compile_features(amr_driver_stm32_hardware PUBLIC cxx_std_17)

if("$ENV{ROS_DISTRO}" STREQUAL "foxy")
  target_compile_definitions(amr_driver_stm32_hardware PRIVATE AMR_DRIVER_ROS2_CONTROL_FOXY)
endif()

target_include_directories(amr_driver_stm32_hardware PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(amr_driver_stm32_hardware
  hardware_interface
  pluginlib
  rclcpp
  rclcpp_lifecycle
)

pluginlib_export_plugin_description_file(
  hardware_interface
  amr_driver_hardware_plugins.xml
)

ament_python_install_package(${PROJECT_NAME})

install(
  TARGETS amr_driver_stm32_hardware
  EXPORT export_amr_driver_stm32_hardware
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(
  DIRECTORY include/
  DESTINATION include
)

install(
  PROGRAMS scripts/amr_driver_node
  DESTINATION lib/${PROJECT_NAME}
)

install(
  DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

install(
  FILES amr_driver_hardware_plugins.xml
  DESTINATION share/${PROJECT_NAME}
)

ament_export_include_directories(include)
ament_export_libraries(amr_driver_stm32_hardware)
ament_export_dependencies(
  hardware_interface
  pluginlib
  rclcpp
  rclcpp_lifecycle
)

ament_package()
