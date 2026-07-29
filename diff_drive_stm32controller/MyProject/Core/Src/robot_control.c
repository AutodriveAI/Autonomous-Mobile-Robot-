#include "robot_control.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "encoder.h"
#include "motor.h"
#include "wheel_pid.h"

/*
 * Low-level STM32 command watchdog.
 *
 * For this diagnostic test, 0U disables the firmware-side timeout so we can
 * check whether the periodic one-second wheel stop is caused by this layer.
 *
 * Restore to 300U after the test for normal safety behavior.
 */
#define COMMAND_TIMEOUT_MS 0U
#define TELEMETRY_PERIOD_MS 50U
#define PID_SET_TELEMETRY_PAUSE_MS 1000U
#define PID_GET_TELEMETRY_PAUSE_MS 3000U
#define TELEMETRY_BUFFER_SIZE 112U
#define UART_RX_LINE_SIZE 32U

#define CONTROL_MODE_STOP 0U
#define CONTROL_MODE_RAW_PWM 1U
#define CONTROL_MODE_SPEED_PID 2U

static UART_HandleTypeDef *robot_uart;
static WheelSpeedController speed_controller;
static uint8_t control_mode = CONTROL_MODE_STOP;
static int left_raw_pwm = 0;
static int right_raw_pwm = 0;
static uint32_t last_valid_command_ms = 0U;
static uint32_t last_telemetry_ms = 0U;
static uint32_t telemetry_pause_until_ms = 0U;

/* A fixed buffer prevents malformed serial traffic from consuming arbitrary memory. */
static uint8_t uart_rx_byte = 0U;
static char uart_rx_line[UART_RX_LINE_SIZE];
static uint8_t uart_rx_index = 0U;
static uint8_t uart_rx_overflow = 0U;
static char telemetry_buffer[TELEMETRY_BUFFER_SIZE];

/* Send short acknowledgements for tuning commands; telemetry remains "left,right". */
static void RobotControl_SendReply(const char *reply)
{
  HAL_UART_Transmit(robot_uart, (uint8_t *)reply, (uint16_t)strlen(reply), 10U);
}

/* Suspend only the periodic encoder text, leaving control and UART reception active. */
static void RobotControl_PauseTelemetry(uint32_t now_ms, uint32_t pause_ms)
{
  telemetry_pause_until_ms = now_ms + pause_ms;
  last_telemetry_ms = now_ms;
}

/* This signed comparison also works if the millisecond HAL tick counter wraps. */
static bool RobotControl_TelemetryIsPaused(uint32_t now_ms)
{
  return ((int32_t)(now_ms - telemetry_pause_until_ms) < 0);
}

/* Print gains to three decimal places without requiring floating-point printf support. */
static void RobotControl_SendPidGains(void)
{
  WheelPidGains gains;
  long kp_milli;
  long ki_milli;
  long kd_milli;
  int length;

  WheelPid_GetGains(&gains);
  kp_milli = (long)((gains.kp * 1000.0f) + 0.5f);
  ki_milli = (long)((gains.ki * 1000.0f) + 0.5f);
  kd_milli = (long)((gains.kd * 1000.0f) + 0.5f);

  length = snprintf(telemetry_buffer, sizeof(telemetry_buffer),
      "PID,%ld.%03ld,%ld.%03ld,%ld.%03ld\r\n",
      kp_milli / 1000L, kp_milli % 1000L,
      ki_milli / 1000L, ki_milli % 1000L,
      kd_milli / 1000L, kd_milli % 1000L);

  if ((length > 0) && (length < (int)sizeof(telemetry_buffer)))
  {
    HAL_UART_Transmit(robot_uart, (uint8_t *)telemetry_buffer,
        (uint16_t)length, 10U);
  }
}

static int RobotControl_ClampPwm(long pwm)
{
  if (pwm > 999L)
  {
    return 999;
  }
  if (pwm < -999L)
  {
    return -999;
  }

  return (int)pwm;
}

static void RobotControl_Stop(uint32_t now_ms)
{
  control_mode = CONTROL_MODE_STOP;
  left_raw_pwm = 0;
  right_raw_pwm = 0;
  WheelSpeedController_Stop(&speed_controller, now_ms,
      Encoder_GetLeftCount(), Encoder_GetRightCount());
  Motor_Stop();
}

/* Parse complete serial commands after RobotControl_ProcessByte finds a newline. */
static void RobotControl_ProcessLine(char *line)
{
  char *end_ptr;
  char *right_text;
  long left_value;
  long right_value;
  uint32_t now_ms;

  /*
   * P,<kp>,<ki>,<kd> changes gains immediately, but does not write Flash.
   * SAVE is deliberately separate: Flash has limited erase endurance and the
   * write operation should happen only after the user accepts a tuning value.
   */
  if (strcmp(line, "SAVE") == 0)
  {
    now_ms = HAL_GetTick();
    RobotControl_Stop(now_ms);  /* Never erase Flash while the robot is moving. */
    if (WheelPid_SaveGains())
    {
      RobotControl_SendReply("OK,SAVE\r\n");
    }
    else
    {
      RobotControl_SendReply("ERR,SAVE\r\n");
    }
    return;
  }

  /* G means "get PID gains" and reports Kp, Ki, then Kd. */
  if (strcmp(line, "G") == 0)
  {
    now_ms = HAL_GetTick();
    last_valid_command_ms = now_ms;
    RobotControl_PauseTelemetry(now_ms, PID_GET_TELEMETRY_PAUSE_MS);
    RobotControl_SendPidGains();
    return;
  }

  /* R means "reset encoder totals"; it does not change PID gains or targets. */
  if (strcmp(line, "R") == 0)
  {
    Encoder_ResetCounts();
    now_ms = HAL_GetTick();
    WheelSpeedController_ResetPidHistory(&speed_controller, now_ms,
        Encoder_GetLeftCount(), Encoder_GetRightCount());
    last_valid_command_ms = now_ms;
    RobotControl_PauseTelemetry(now_ms, PID_SET_TELEMETRY_PAUSE_MS);
    RobotControl_SendReply("OK,R\r\n");
    return;
  }

  if ((line[0] == 'P') && (line[1] == ','))
  {
    char *gain_text;
    float kp;
    float ki;
    float kd;

    kp = strtof(&line[2], &end_ptr);
    if ((end_ptr == &line[2]) || (*end_ptr != ','))
    {
      return;
    }
    gain_text = end_ptr + 1;
    ki = strtof(gain_text, &end_ptr);
    if ((end_ptr == gain_text) || (*end_ptr != ','))
    {
      return;
    }
    gain_text = end_ptr + 1;
    kd = strtof(gain_text, &end_ptr);
    if ((end_ptr == gain_text) || (*end_ptr != '\0'))
    {
      return;
    }

    if (!WheelPid_SetGains(kp, ki, kd))
    {
      RobotControl_SendReply("ERR,P\r\n");
      return;
    }

    now_ms = HAL_GetTick();
    WheelSpeedController_ResetPidHistory(&speed_controller, now_ms,
        Encoder_GetLeftCount(), Encoder_GetRightCount());
    last_valid_command_ms = now_ms;
    RobotControl_PauseTelemetry(now_ms, PID_SET_TELEMETRY_PAUSE_MS);
    RobotControl_SendReply("OK,P\r\n");
    return;
  }

  if (((line[0] != 'C') && (line[0] != 'V')) || (line[1] != ','))
  {
    return;
  }

  left_value = strtol(&line[2], &end_ptr, 10);
  if ((end_ptr == &line[2]) || (*end_ptr != ','))
  {
    return;
  }

  right_text = end_ptr + 1;
  right_value = strtol(right_text, &end_ptr, 10);
  if ((end_ptr == right_text) || (*end_ptr != '\0'))
  {
    return;
  }

  now_ms = HAL_GetTick();

  if (line[0] == 'C')
  {
    /* Raw PWM mode is retained for bench diagnostics and bypasses PID. */
    left_raw_pwm = RobotControl_ClampPwm(left_value);
    right_raw_pwm = RobotControl_ClampPwm(right_value);
    WheelSpeedController_Stop(&speed_controller, now_ms,
        Encoder_GetLeftCount(), Encoder_GetRightCount());
    control_mode = CONTROL_MODE_RAW_PWM;
  }
  else
  {
    WheelSpeedController_SetTargets(&speed_controller, (float)left_value,
        (float)right_value, now_ms, Encoder_GetLeftCount(),
        Encoder_GetRightCount());
    control_mode = CONTROL_MODE_SPEED_PID;
  }

  /* Only a fully valid command refreshes the motor safety timeout. */
  last_valid_command_ms = now_ms;
}

/* Add one non-blocking UART byte to the current command line. */
static void RobotControl_ProcessByte(uint8_t byte)
{
  if (byte == '\r')
  {
    return;  /* Supports Windows CRLF without storing the carriage return. */
  }

  if (byte == '\n')
  {
    if (uart_rx_overflow == 0U)
    {
      uart_rx_line[uart_rx_index] = '\0';
      RobotControl_ProcessLine(uart_rx_line);
    }

    uart_rx_index = 0U;
    uart_rx_overflow = 0U;
    return;
  }

  if (uart_rx_overflow != 0U)
  {
    return;  /* Ignore excess bytes until the next newline restores alignment. */
  }

  if (uart_rx_index < (UART_RX_LINE_SIZE - 1U))
  {
    uart_rx_line[uart_rx_index] = (char)byte;
    uart_rx_index++;
  }
  else
  {
    uart_rx_overflow = 1U;
  }
}

static void RobotControl_SendTelemetry(uint32_t now_ms)
{
  int length;
  long left_ctps;
  long right_ctps;

  if (RobotControl_TelemetryIsPaused(now_ms))
  {
    return;
  }

  if ((uint32_t)(now_ms - last_telemetry_ms) < TELEMETRY_PERIOD_MS)
  {
    return;
  }

  /*
   * Speeds are kept as float internally, but integer ticks/s keeps the serial
   * output compact and avoids requiring floating-point printf support.
   */
  left_ctps = (long)WheelSpeedController_GetLeftMeasuredTicksPerSecond(
      &speed_controller);
  right_ctps = (long)WheelSpeedController_GetRightMeasuredTicksPerSecond(
      &speed_controller);

  length = snprintf(telemetry_buffer, sizeof(telemetry_buffer),
      /* Fixed-width fields keep the columns aligned as values gain digits. */
      "LTicks:%-10lu   LPWM:%-6d   LCTPS:%-7ld    "
      "RTicks:%-10lu   RPWM:%-6d   RCTPS:%-7ld\r\n",
      (unsigned long)Encoder_GetLeftCount(),
      WheelSpeedController_GetLeftPwm(&speed_controller), left_ctps,
      (unsigned long)Encoder_GetRightCount(),
      WheelSpeedController_GetRightPwm(&speed_controller), right_ctps);

  if ((length > 0) && (length < (int)sizeof(telemetry_buffer)))
  {
    HAL_UART_Transmit(robot_uart, (uint8_t *)telemetry_buffer,
        (uint16_t)length, 10U);
  }

  last_telemetry_ms = now_ms;
}

void RobotControl_Init(UART_HandleTypeDef *uart)
{
  uint32_t now_ms = HAL_GetTick();

  robot_uart = uart;
  /* Load a valid record saved by SAVE, otherwise retain compiled-in defaults. */
  WheelPid_LoadSavedGains();
  last_valid_command_ms = now_ms;
  last_telemetry_ms = now_ms;
  telemetry_pause_until_ms = now_ms;
  WheelSpeedController_Init(&speed_controller, now_ms,
      Encoder_GetLeftCount(), Encoder_GetRightCount());
}

void RobotControl_Update(void)
{
  uint32_t now_ms;

  /* Zero timeout means this read never waits for serial data. */
  if (HAL_UART_Receive(robot_uart, &uart_rx_byte, 1U, 0U) == HAL_OK)
  {
    RobotControl_ProcessByte(uart_rx_byte);
  }

  now_ms = HAL_GetTick();

  if ((COMMAND_TIMEOUT_MS > 0U) &&
      ((uint32_t)(now_ms - last_valid_command_ms) >= COMMAND_TIMEOUT_MS))
  {
    if (control_mode != CONTROL_MODE_STOP)
    {
      RobotControl_Stop(now_ms);
    }
  }
  else if (control_mode == CONTROL_MODE_RAW_PWM)
  {
    Motor_SetLeftSpeed(left_raw_pwm);
    Motor_SetRightSpeed(right_raw_pwm);
  }
  else if (control_mode == CONTROL_MODE_SPEED_PID)
  {
    WheelSpeedController_Update(&speed_controller, now_ms,
        Encoder_GetLeftCount(), Encoder_GetRightCount());
    Motor_SetLeftSpeed(WheelSpeedController_GetLeftPwm(&speed_controller));
    Motor_SetRightSpeed(WheelSpeedController_GetRightPwm(&speed_controller));
  }
  else
  {
    Motor_Stop();
  }

  RobotControl_SendTelemetry(now_ms);
}
