#include "wheel_pid.h"

#include <string.h>

#include "main.h"

/*
 * This file implements two independent wheel-speed controllers.
 * Input unit: encoder ticks per second.  Output unit: PWM from -999 to +999.
 * The controller is called frequently, but updates its PWM only every 50 ms.
 */

/* Compiled-in gains used on a new board or when no valid saved record exists. */
#define WHEEL_PID_DEFAULT_KP 3.0f
#define WHEEL_PID_DEFAULT_KI 0.5f
#define WHEEL_PID_DEFAULT_KD 0.0f

/* Reject accidental or corrupt gain values before they can drive a motor. */
#define WHEEL_PID_MAX_GAIN 100.0f

/* STM32F401 sector 7 is 128 KiB at the end of its 512 KiB internal Flash. */
#define WHEEL_PID_FLASH_ADDRESS 0x08060000U
#define WHEEL_PID_FLASH_MAGIC 0x50494431U  /* ASCII-like identifier: "PID1". */
#define WHEEL_PID_FLASH_VERSION 1U

/*
 * Six 32-bit words are programmed at the start of the reserved sector.
 * Storing each float as its raw bits avoids text parsing and keeps the record
 * compact.  The checksum makes partially written or unrelated Flash invalid.
 */
typedef struct
{
  uint32_t magic;
  uint32_t version;
  uint32_t kp_bits;
  uint32_t ki_bits;
  uint32_t kd_bits;
  uint32_t checksum;
} WheelPidFlashRecord;

static WheelPidGains wheel_pid_gains =
{
  WHEEL_PID_DEFAULT_KP,
  WHEEL_PID_DEFAULT_KI,
  WHEEL_PID_DEFAULT_KD
};

static uint32_t WheelPid_FloatToBits(float value)
{
  uint32_t bits;

  memcpy(&bits, &value, sizeof(bits));
  return bits;
}

static float WheelPid_BitsToFloat(uint32_t bits)
{
  float value;

  memcpy(&value, &bits, sizeof(value));
  return value;
}

static uint32_t WheelPid_RecordChecksum(const WheelPidFlashRecord *record)
{
  return record->magic ^ record->version ^ record->kp_bits ^ record->ki_bits ^
      record->kd_bits ^ 0xA5A55A5AU;
}

/* A value which is not equal to itself is NaN, so no math-library call is needed. */
static bool WheelPid_GainIsValid(float gain)
{
  return (gain == gain) && (gain >= 0.0f) && (gain <= WHEEL_PID_MAX_GAIN);
}

/* Prevent integral windup when a wheel is stalled or output is saturated. */
#define WHEEL_PID_INTEGRAL_LIMIT 300.0f

/* Keep accidental serial requests within a reasonable initial speed range. */
static float WheelPid_ClampTarget(float target)
{
  if (target > WHEEL_PID_MAX_TARGET_TICKS_PER_SECOND)
  {
    return WHEEL_PID_MAX_TARGET_TICKS_PER_SECOND;
  }
  if (target < -WHEEL_PID_MAX_TARGET_TICKS_PER_SECOND)
  {
    return -WHEEL_PID_MAX_TARGET_TICKS_PER_SECOND;
  }

  return target;
}

/*
 * Clear values retained from old PID samples.  Saving current encoder counts
 * makes the next speed sample measure only pulses that arrive after this call.
 */
static void WheelPid_ResetHistory(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count)
{
  controller->last_update_ms = now_ms;       /* Time base for the next sample. */
  controller->left_previous_count = left_count;
  controller->right_previous_count = right_count;
  controller->left_integral = 0.0f;          /* Forget accumulated past error. */
  controller->right_integral = 0.0f;
  controller->left_previous_error = 0.0f;    /* No prior derivative sample. */
  controller->right_previous_error = 0.0f;
  controller->left_measured_ticks_per_second = 0.0f;
  controller->right_measured_ticks_per_second = 0.0f;
  controller->left_pwm = 0;                  /* Begin safely with stopped motors. */
  controller->right_pwm = 0;
}

/*
 * Run one PID calculation for one wheel.
 * PWM = Kp * error + Ki * integral(error) + Kd * derivative(error)
 * Pointers allow each wheel's integral and previous error to persist between calls.
 */
static int WheelPid_RunOne(float target, float measured, float *integral,
    float *previous_error, float elapsed_seconds)
{
  float error;       /* Desired speed minus measured speed, in ticks/s. */
  float derivative;  /* Change in error per second. */
  float output;      /* PID result before it is limited to legal PWM. */

  /* A stopped wheel has zero commanded PWM; single-channel feedback has no direction. */
  if (target == 0.0f)
  {
    *integral = 0.0f;
    *previous_error = 0.0f;
    return 0;
  }

  error = target - measured;

  /* Add error multiplied by time: this is the integral part of PID. */
  *integral += error * elapsed_seconds;

  if (*integral > WHEEL_PID_INTEGRAL_LIMIT)
  {
    *integral = WHEEL_PID_INTEGRAL_LIMIT;
  }
  else if (*integral < -WHEEL_PID_INTEGRAL_LIMIT)
  {
    *integral = -WHEEL_PID_INTEGRAL_LIMIT;
  }

  /* Divide error change by time to obtain the derivative part of PID. */
  derivative = (error - *previous_error) / elapsed_seconds;
  *previous_error = error;  /* Save this reading for the next update. */

  /* Combine proportional, integral, and derivative contributions. */
  output = (wheel_pid_gains.kp * error) +
      (wheel_pid_gains.ki * *integral) +
      (wheel_pid_gains.kd * derivative);

  /*
   * A speed controller must not reverse a wheel merely because one sampled
   * speed is above its target.  With a forward target, negative PWM would
   * drive the L298N backward and create the visible forward/backward jitter.
   * Instead, zero PWM lets an overspeeding wheel coast down naturally.
   *
   * The equivalent rule is applied for a backward target: it may command
   * reverse PWM or zero, but never a forward correction.
   */
  if (target > 0.0f)
  {
    if (output > 999.0f)
    {
      return 999;
    }
    if (output < 0.0f)
    {
      return 0;
    }
  }
  else
  {
    if (output < -999.0f)
    {
      return -999;
    }
    if (output > 0.0f)
    {
      return 0;
    }
  }

  return (int)output;
}

void WheelSpeedController_Init(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count)
{
  /* No V command has arrived at power-up, so both requested wheel speeds are zero. */
  controller->left_target_ticks_per_second = 0.0f;
  controller->right_target_ticks_per_second = 0.0f;
  WheelPid_ResetHistory(controller, now_ms, left_count, right_count);
}

void WheelSpeedController_SetTargets(WheelSpeedController *controller,
    float left_ticks_per_second, float right_ticks_per_second, uint32_t now_ms,
    uint32_t left_count, uint32_t right_count)
{
  /* Clamp incoming serial setpoints before they become motor-speed requests. */
  float new_left = WheelPid_ClampTarget(left_ticks_per_second);
  float new_right = WheelPid_ClampTarget(right_ticks_per_second);
  bool direction_changed;

  /* A negative product means the old and new targets have opposite signs. */
  direction_changed = ((new_left * controller->left_target_ticks_per_second) < 0.0f) ||
      ((new_right * controller->right_target_ticks_per_second) < 0.0f);

  controller->left_target_ticks_per_second = new_left;
  controller->right_target_ticks_per_second = new_right;

  /* Preserve PID history for ordinary speed updates; reset only on reversal. */
  if (direction_changed)
  {
    WheelPid_ResetHistory(controller, now_ms, left_count, right_count);
  }
}

void WheelSpeedController_Stop(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count)
{
  /* Clearing targets makes subsequent PID updates request zero PWM. */
  controller->left_target_ticks_per_second = 0.0f;
  controller->right_target_ticks_per_second = 0.0f;
  WheelPid_ResetHistory(controller, now_ms, left_count, right_count);
}

void WheelSpeedController_ResetPidHistory(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count)
{
  float left_target = controller->left_target_ticks_per_second;
  float right_target = controller->right_target_ticks_per_second;

  /* Reset integral/derivative/count history, then retain the active V command. */
  WheelPid_ResetHistory(controller, now_ms, left_count, right_count);
  controller->left_target_ticks_per_second = left_target;
  controller->right_target_ticks_per_second = right_target;
}

bool WheelSpeedController_Update(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count)
{
  /* Unsigned subtraction remains valid if HAL_GetTick() eventually wraps. */
  uint32_t elapsed_ms = (uint32_t)(now_ms - controller->last_update_ms);
  uint32_t left_delta;       /* Pulses received since the prior PID sample. */
  uint32_t right_delta;
  float elapsed_seconds;     /* Same interval expressed in seconds. */
  float left_measured;       /* Measured left speed in ticks/s. */
  float right_measured;

  if (elapsed_ms < WHEEL_PID_PERIOD_MS)
  {
    return false;
  }

  /* Convert milliseconds to seconds because targets use ticks per second. */
  elapsed_seconds = (float)elapsed_ms / 1000.0f;
  controller->last_update_ms = now_ms;

  /* Unsigned subtraction remains valid if a 32-bit count eventually wraps. */
  left_delta = left_count - controller->left_previous_count;
  right_delta = right_count - controller->right_previous_count;
  controller->left_previous_count = left_count;
  controller->right_previous_count = right_count;

  /* Speed is count change divided by elapsed time: ticks / second. */
  left_measured = (float)left_delta / elapsed_seconds;
  right_measured = (float)right_delta / elapsed_seconds;

  /* With one channel per wheel, requested direction supplies the speed sign. */
  if (controller->left_target_ticks_per_second < 0.0f)
  {
    left_measured = -left_measured;
  }
  if (controller->right_target_ticks_per_second < 0.0f)
  {
    right_measured = -right_measured;
  }

  /* Retain these values so the serial telemetry can show what PID measured. */
  controller->left_measured_ticks_per_second = left_measured;
  controller->right_measured_ticks_per_second = right_measured;

  /* Save the new PWM values; RobotControl applies them to the motor module. */
  controller->left_pwm = WheelPid_RunOne(controller->left_target_ticks_per_second,
      left_measured, &controller->left_integral, &controller->left_previous_error,
      elapsed_seconds);
  controller->right_pwm = WheelPid_RunOne(controller->right_target_ticks_per_second,
      right_measured, &controller->right_integral, &controller->right_previous_error,
      elapsed_seconds);

  return true;
}

int WheelSpeedController_GetLeftPwm(const WheelSpeedController *controller)
{
  return controller->left_pwm;
}

int WheelSpeedController_GetRightPwm(const WheelSpeedController *controller)
{
  return controller->right_pwm;
}

float WheelSpeedController_GetLeftMeasuredTicksPerSecond(
    const WheelSpeedController *controller)
{
  return controller->left_measured_ticks_per_second;
}

float WheelSpeedController_GetRightMeasuredTicksPerSecond(
    const WheelSpeedController *controller)
{
  return controller->right_measured_ticks_per_second;
}

void WheelPid_LoadSavedGains(void)
{
  const WheelPidFlashRecord *record =
      (const WheelPidFlashRecord *)WHEEL_PID_FLASH_ADDRESS;
  WheelPidGains saved_gains;

  /* An erased sector or a record from another firmware version is ignored. */
  if ((record->magic != WHEEL_PID_FLASH_MAGIC) ||
      (record->version != WHEEL_PID_FLASH_VERSION) ||
      (record->checksum != WheelPid_RecordChecksum(record)))
  {
    return;
  }

  saved_gains.kp = WheelPid_BitsToFloat(record->kp_bits);
  saved_gains.ki = WheelPid_BitsToFloat(record->ki_bits);
  saved_gains.kd = WheelPid_BitsToFloat(record->kd_bits);

  if (WheelPid_GainIsValid(saved_gains.kp) &&
      WheelPid_GainIsValid(saved_gains.ki) &&
      WheelPid_GainIsValid(saved_gains.kd))
  {
    wheel_pid_gains = saved_gains;
  }
}

bool WheelPid_SetGains(float kp, float ki, float kd)
{
  if (!WheelPid_GainIsValid(kp) || !WheelPid_GainIsValid(ki) ||
      !WheelPid_GainIsValid(kd))
  {
    return false;
  }

  wheel_pid_gains.kp = kp;
  wheel_pid_gains.ki = ki;
  wheel_pid_gains.kd = kd;
  return true;
}

void WheelPid_GetGains(WheelPidGains *gains)
{
  if (gains != NULL)
  {
    *gains = wheel_pid_gains;
  }
}

bool WheelPid_SaveGains(void)
{
  WheelPidFlashRecord record;
  FLASH_EraseInitTypeDef erase_config;
  uint32_t sector_error = 0U;
  const uint32_t *record_words;
  uint32_t address;
  uint32_t word_index;

  record.magic = WHEEL_PID_FLASH_MAGIC;
  record.version = WHEEL_PID_FLASH_VERSION;
  record.kp_bits = WheelPid_FloatToBits(wheel_pid_gains.kp);
  record.ki_bits = WheelPid_FloatToBits(wheel_pid_gains.ki);
  record.kd_bits = WheelPid_FloatToBits(wheel_pid_gains.kd);
  record.checksum = WheelPid_RecordChecksum(&record);

  if (HAL_FLASH_Unlock() != HAL_OK)
  {
    return false;
  }

  erase_config.TypeErase = FLASH_TYPEERASE_SECTORS;
  erase_config.Sector = FLASH_SECTOR_7;
  erase_config.NbSectors = 1U;
  erase_config.VoltageRange = FLASH_VOLTAGE_RANGE_3;

  if (HAL_FLASHEx_Erase(&erase_config, &sector_error) != HAL_OK)
  {
    HAL_FLASH_Lock();
    return false;
  }

  record_words = (const uint32_t *)&record;
  address = WHEEL_PID_FLASH_ADDRESS;
  for (word_index = 0U;
      word_index < (sizeof(record) / sizeof(record_words[0])); word_index++)
  {
    if (HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, address,
        record_words[word_index]) != HAL_OK)
    {
      HAL_FLASH_Lock();
      return false;
    }
    address += sizeof(uint32_t);
  }

  HAL_FLASH_Lock();

  /* Read back the just-written record, including its checksum, before ACKing. */
  return (((const WheelPidFlashRecord *)WHEEL_PID_FLASH_ADDRESS)->magic ==
      WHEEL_PID_FLASH_MAGIC) &&
      (((const WheelPidFlashRecord *)WHEEL_PID_FLASH_ADDRESS)->checksum ==
      record.checksum);
}
