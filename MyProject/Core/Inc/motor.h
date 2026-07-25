#ifndef MOTOR_H
#define MOTOR_H

#include "main.h"

/*
 * Configure the two PWM channels used by each L298N motor input pair.
 * The forward and reverse channel arguments encode the verified wiring polarity.
 */
void Motor_Init(TIM_HandleTypeDef *left_timer, uint32_t left_forward_channel,
    uint32_t left_reverse_channel, TIM_HandleTypeDef *right_timer,
    uint32_t right_forward_channel, uint32_t right_reverse_channel);

/* Set signed PWM values in the range -999 (backward) to +999 (forward). */
void Motor_SetLeftSpeed(int speed);
void Motor_SetRightSpeed(int speed);
void Motor_Stop(void);

#endif /* MOTOR_H */
