#ifndef ENCODER_H
#define ENCODER_H

#include "main.h"

/*
 * Prepare encoder reading.
 *
 * The arguments are kept so main.c does not need a large interface change, but
 * the present HC-020K test path does not use timer capture interrupts.  We read
 * PB6 and PA8 as normal digital inputs and debounce them in software.
 */
void Encoder_Init(TIM_HandleTypeDef *left_timer, TIM_HandleTypeDef *right_timer);

/*
 * Poll both encoder input pins once.
 *
 * Call this frequently from while(1).  It updates the internal pulse counters
 * whenever a debounced LOW-to-HIGH transition is seen.
 */
void Encoder_Update(void);

/* Each function returns the monotonically increasing raw pulse count. */
uint32_t Encoder_GetLeftCount(void);
uint32_t Encoder_GetRightCount(void);

/* Set both software pulse totals to zero for a fresh distance measurement. */
void Encoder_ResetCounts(void);

#endif /* ENCODER_H */
