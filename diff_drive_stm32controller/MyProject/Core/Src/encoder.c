#include "encoder.h"

/* These pointers identify which CubeMX timer belongs to each physical wheel. */
static TIM_HandleTypeDef *left_encoder_timer;
static TIM_HandleTypeDef *right_encoder_timer;

/* volatile is required because these values change inside capture interrupts. */
static volatile uint32_t left_encoder_count = 0U;
static volatile uint32_t right_encoder_count = 0U;

void Encoder_Init(TIM_HandleTypeDef *left_timer, TIM_HandleTypeDef *right_timer)
{
  left_encoder_timer = left_timer;    /* TIM4 / PB6 / D10 */
  right_encoder_timer = right_timer;  /* TIM1 / PA8 / D7 */

  /*
   * CubeMX configures CH1 as rising-edge Input Capture and enables NVIC.
   * Starting with _IT enables one HAL callback for every captured pulse.
   */
  if (HAL_TIM_IC_Start_IT(left_encoder_timer, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }

  if (HAL_TIM_IC_Start_IT(right_encoder_timer, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
}

uint32_t Encoder_GetLeftCount(void)
{
  return left_encoder_count;
}

uint32_t Encoder_GetRightCount(void)
{
  return right_encoder_count;
}

void Encoder_ResetCounts(void)
{
  uint32_t interrupt_state = __get_PRIMASK();

  /*
   * A capture interrupt can increment either count at any instant.  Briefly
   * disable interrupts so the two assignments form one consistent reset.
   */
  __disable_irq();
  left_encoder_count = 0U;
  right_encoder_count = 0U;

  /* Preserve the caller's prior interrupt state instead of always enabling it. */
  if (interrupt_state == 0U)
  {
    __enable_irq();
  }
}

/*
 * CubeMX's generated TIM1_CC_IRQHandler and TIM4_IRQHandler call HAL_TIM_IRQHandler.
 * HAL then calls this callback after a configured input-capture event.
 */
void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
  if ((htim == left_encoder_timer) &&
      (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_1))
  {
    left_encoder_count++;
  }
  else if ((htim == right_encoder_timer) &&
           (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_1))
  {
    right_encoder_count++;
  }
}
