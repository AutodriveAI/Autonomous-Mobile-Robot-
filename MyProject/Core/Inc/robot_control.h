#ifndef ROBOT_CONTROL_H
#define ROBOT_CONTROL_H

#include "main.h"

/* Owns serial commands, command timeout, PID selection, and encoder telemetry. */
void RobotControl_Init(UART_HandleTypeDef *uart);
void RobotControl_Update(void);

#endif /* ROBOT_CONTROL_H */
