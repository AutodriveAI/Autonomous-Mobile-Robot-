/*
 * Header files expose the public interface of a module.
 *
 * robot_control.c includes this file so it knows:
 * - the WheelSpeedController data type,
 * - the tuning-related limits shared with wheel_pid.c, and
 * - the functions it may call.
 *
 * The actual PID algorithm remains private in wheel_pid.c.  This separation
 * prevents other source files from needing to know its internal helper code.
 */

/* Include guard: prevents this header being processed more than once per .c file. */
#ifndef WHEEL_PID_H
#define WHEEL_PID_H

/* bool/true/false are used by the Update function's return value. */
#include <stdbool.h>
/* uint32_t is used for millisecond time and encoder counter values. */
#include <stdint.h>

/*
 * PID calculation interval.  50 ms equals 0.05 s, which means 20 updates/s.
 * Both wheel-speed measurement and PID output updates use this period.
 */
#define WHEEL_PID_PERIOD_MS 50U

/*
 * Safety limit for V commands, in encoder ticks per second.
 * With 100 ticks/wheel revolution, 1000 ticks/s equals 10 wheel revolutions/s.
 */
#define WHEEL_PID_MAX_TARGET_TICKS_PER_SECOND 1000.0f

/*
 * The three adjustable PID gains.  They are shared by the left and right
 * wheel controllers for now, which makes initial tuning much simpler.
 */
typedef struct
{
  float kp;
  float ki;
  float kd;
} WheelPidGains;

/*
 * All state needed to control both wheels.
 *
 * The application creates one WheelSpeedController variable and passes its
 * address to every function below.  Keeping state in this structure avoids
 * unrelated global variables and would allow multiple controllers if needed.
 */
typedef struct
{
  /* Current V-command targets. Positive is forward; negative is backward. */
  float left_target_ticks_per_second;
  float right_target_ticks_per_second;

  /* Stored I terms: accumulated speed error from previous PID updates. */
  float left_integral;
  float right_integral;

  /* Stored error from the prior update, required to calculate the D term. */
  float left_previous_error;
  float right_previous_error;

  /* Time and raw encoder totals saved at the previous PID sample. */
  uint32_t last_update_ms;
  uint32_t left_previous_count;
  uint32_t right_previous_count;

  /* Latest speeds calculated from encoder ticks, in signed ticks per second. */
  float left_measured_ticks_per_second;
  float right_measured_ticks_per_second;

  /* Most recent calculated outputs, ready for Motor_SetLeft/RightSpeed(). */
  int left_pwm;
  int right_pwm;
} WheelSpeedController;

/*
 * Initialise a controller in the stopped state.
 *
 * now_ms is HAL_GetTick(); encoder counts are the values currently read from
 * the two encoders.  Saving them establishes the starting point for deltas.
 */
void WheelSpeedController_Init(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count);

/*
 * Store a new signed target speed for each wheel, in ticks/s.
 * Normal speed changes preserve PID history; a direction reversal resets it.
 */
void WheelSpeedController_SetTargets(WheelSpeedController *controller,
    float left_ticks_per_second, float right_ticks_per_second, uint32_t now_ms,
    uint32_t left_count, uint32_t right_count);

/* Clear targets, stored PID history, and PWM output for a safe stop. */
void WheelSpeedController_Stop(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count);

/*
 * Clear only the retained PID calculation history while leaving the requested
 * wheel speeds unchanged.  This is used after changing tuning gains live.
 */
void WheelSpeedController_ResetPidHistory(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count);

/*
 * Calculate new wheel PWM values when at least WHEEL_PID_PERIOD_MS elapsed.
 *
 * Returns true only when a new PID result was produced.  Returns false when
 * called too soon, leaving the previous PWM outputs unchanged.
 */
bool WheelSpeedController_Update(WheelSpeedController *controller,
    uint32_t now_ms, uint32_t left_count, uint32_t right_count);

/* Read the latest PID result.  Values are always clamped to -999 through +999. */
int WheelSpeedController_GetLeftPwm(const WheelSpeedController *controller);
int WheelSpeedController_GetRightPwm(const WheelSpeedController *controller);

/* Read the latest encoder-derived speed used by the PID calculation. */
float WheelSpeedController_GetLeftMeasuredTicksPerSecond(
    const WheelSpeedController *controller);
float WheelSpeedController_GetRightMeasuredTicksPerSecond(
    const WheelSpeedController *controller);

/*
 * Runtime tuning and non-volatile storage API.
 *
 * WheelPid_LoadSavedGains() is called once at start-up.  If no valid saved
 * record exists, it leaves the safe compiled-in default gains active.
 * WheelPid_SaveGains() writes the current gains to reserved internal Flash;
 * it must be called explicitly, not after every tuning command.
 */
void WheelPid_LoadSavedGains(void);
bool WheelPid_SetGains(float kp, float ki, float kd);
void WheelPid_GetGains(WheelPidGains *gains);
bool WheelPid_SaveGains(void);

#endif /* WHEEL_PID_H */
