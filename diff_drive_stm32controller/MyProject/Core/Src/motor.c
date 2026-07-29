#include "motor.h"

typedef struct
{
  TIM_HandleTypeDef *timer;
  uint32_t forward_channel;
  uint32_t reverse_channel;
} MotorChannelPair;

static MotorChannelPair left_motor;
static MotorChannelPair right_motor;

/*
 * Motor direction calibration.
 *
 * ROS and the firmware command convention are:
 *   positive speed  = robot/wheel should move forward
 *   negative speed  = robot/wheel should move backward
 *
 * The physical motor wiring currently produces the opposite motion: a positive
 * command drives the robot backward.  Keep the wiring and CubeMX pin mapping
 * unchanged, and fix that sign here in the motor output layer.
 *
 * If later only one side is wrong, change only that side's sign.
 * Valid values:
 *   +1 = keep command sign
 *   -1 = invert command sign
 */
#define LEFT_MOTOR_DIRECTION_SIGN   (-1)
#define RIGHT_MOTOR_DIRECTION_SIGN  (-1)

static int Motor_ClampPwm(int speed)
{
  if (speed > 999)
  {
    return 999;
  }

  if (speed < -999)
  {
    return -999;
  }

  return speed;
}

/* Apply one signed PWM value to the two L298N input pins for one motor. */
static void Motor_ApplySpeed(const MotorChannelPair *motor, int speed)
{
  speed = Motor_ClampPwm(speed);

  if (speed > 0)
  {
    /* Forward: PWM on the channel verified to rotate this wheel forward. */
    __HAL_TIM_SET_COMPARE(motor->timer, motor->forward_channel, speed);
    __HAL_TIM_SET_COMPARE(motor->timer, motor->reverse_channel, 0);
  }
  else if (speed < 0)
  {
    /* Backward: PWM on the opposite L298N input. */
    __HAL_TIM_SET_COMPARE(motor->timer, motor->forward_channel, 0);
    __HAL_TIM_SET_COMPARE(motor->timer, motor->reverse_channel, -speed);
  }
  else
  {
    /* Both L298N inputs low: coast/stop. */
    __HAL_TIM_SET_COMPARE(motor->timer, motor->forward_channel, 0);
    __HAL_TIM_SET_COMPARE(motor->timer, motor->reverse_channel, 0);
  }
}

void Motor_Init(TIM_HandleTypeDef *left_timer, uint32_t left_forward_channel,
    uint32_t left_reverse_channel, TIM_HandleTypeDef *right_timer,
    uint32_t right_forward_channel, uint32_t right_reverse_channel)
{
  left_motor.timer = left_timer;
  left_motor.forward_channel = left_forward_channel;
  left_motor.reverse_channel = left_reverse_channel;

  right_motor.timer = right_timer;
  right_motor.forward_channel = right_forward_channel;
  right_motor.reverse_channel = right_reverse_channel;

  /* PWM must be started once before compare-register changes affect the pins. */
  HAL_TIM_PWM_Start(left_timer, left_forward_channel);
  HAL_TIM_PWM_Start(left_timer, left_reverse_channel);
  HAL_TIM_PWM_Start(right_timer, right_forward_channel);
  HAL_TIM_PWM_Start(right_timer, right_reverse_channel);

  Motor_Stop();
}

void Motor_SetLeftSpeed(int speed)
{
  Motor_ApplySpeed(&left_motor, LEFT_MOTOR_DIRECTION_SIGN * speed);
}

void Motor_SetRightSpeed(int speed)
{
  Motor_ApplySpeed(&right_motor, RIGHT_MOTOR_DIRECTION_SIGN * speed);
}

void Motor_Stop(void)
{
  Motor_ApplySpeed(&left_motor, 0);
  Motor_ApplySpeed(&right_motor, 0);
}
