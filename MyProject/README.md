# STM32 Differential-Drive Robot Firmware

Firmware for an STM32 NUCLEO-F401RE differential-drive robot. Build and flash
it with STM32CubeIDE. Serial communication uses USART2 through the ST-LINK
virtual COM port at **115200 baud**.

## Serial commands

Set the serial monitor line ending to **Newline** or **Both NL & CR**. Commands
are processed only after the terminating newline.

| Command | Meaning | Response |
| --- | --- | --- |
| `C,<left_pwm>,<right_pwm>` | Drive wheels in raw PWM mode; bypasses speed PID. | No acknowledgement; encoder telemetry continues. |
| `V,<left_ticks_s>,<right_ticks_s>` | Set wheel-speed targets and enable speed PID mode. | No acknowledgement; encoder telemetry continues. |
| `P,<kp>,<ki>,<kd>` | Change PID gains immediately in RAM. Does **not** save them across reset. | `OK,P` or `ERR,P` |
| `G` | Print the active PID gains in `Kp, Ki, Kd` order. Telemetry pauses for 3 seconds. | `PID,<kp>,<ki>,<kd>` |
| `R` | Reset both encoder totals to zero. PID gains and requested speeds are unchanged; telemetry pauses for 1 second. | `OK,R` |
| `SAVE` | Stop the motors and save the active PID gains permanently. | `OK,SAVE` or `ERR,SAVE` |

Examples:

```text
C,300,300
V,150,150
P,3.0,0.5,0.0
G
R
SAVE
```

## Limits and conventions

- Raw PWM values are clamped to **-999 through +999**.
- PID speed targets are clamped to **-1000 through +1000 ticks/second**.
- PID gains `Kp`, `Ki`, and `Kd` must each be in the range **0 through 100**.
- After a successful `P` command, encoder telemetry pauses for **1 second** so
  the `OK,P` reply can be read without intervening encoder lines.
- Positive and negative wheel commands follow the motor direction convention
  configured in `motor.c` (positive means robot-forward in the current setup).
- In `V` PID mode, a positive target can command only positive PWM (or zero),
  and a negative target only negative PWM (or zero). An overspeeding wheel
  coasts rather than being actively driven in the opposite direction.
- Each wheel encoder uses one rising-edge channel and has **100 ticks per wheel
  revolution**.
- Encoder/PID telemetry is sent every **50 ms**, as one line:

  ```text
  LTicks:<left_count> LPWM:<left_pwm> LCTPS:<left_ticks_per_second> RTicks:<right_count> RPWM:<right_pwm> RCTPS:<right_ticks_per_second>
  ```

  Example:

  ```text
  LTicks:1436         LPWM:320      LCTPS:200        RTicks:1224         RPWM:310      RCTPS:200
  ```

  `LCTPS` and `RCTPS` are the latest speeds calculated by the PID loop. They
  update in `V` speed-PID mode; after `C` raw-PWM, stop, or reset commands they
  are reset to zero.

## PID persistence

The STM32F401 has no EEPROM. `SAVE` stores the current gains in the final
128 KiB internal Flash sector (sector 7). The linker script reserves that
sector, so normal firmware programming cannot overwrite the saved gains.

Saved gains are read automatically at boot. Do not use `SAVE` repeatedly while
tuning: Flash sectors have finite erase endurance. Adjust values with `P`, test
them, then use `SAVE` only after choosing a value to keep.
