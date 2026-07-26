#ifndef ENCODER_H
#define ENCODER_H

#include "main.h"

/* Start CubeMX-configured TIM4_CH1 (left) and TIM1_CH1 (right) capture interrupts. */
void Encoder_Init(TIM_HandleTypeDef *left_timer, TIM_HandleTypeDef *right_timer);

/* Each function returns the monotonically increasing raw pulse count. */
uint32_t Encoder_GetLeftCount(void);
uint32_t Encoder_GetRightCount(void);

/* Set both software pulse totals to zero for a fresh distance measurement. */
void Encoder_ResetCounts(void);

#endif /* ENCODER_H */
