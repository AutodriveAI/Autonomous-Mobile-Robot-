#include "encoder.h"

/*
 * HC-020K / LM393 encoder modules can produce very short chatter pulses around
 * the optical switching point.  STM32 hardware input capture is fast enough to
 * count those glitches, which made our readings much larger than expected.
 *
 * For the current slow robot and 20-slit disk, GPIO polling with software
 * debounce is easier to control.  A 5 ms debounce means the signal must remain
 * at a new level for 5 ms before we accept it as real.
 */
#define ENCODER_DEBOUNCE_MS 5U

typedef struct
{
  GPIO_TypeDef *gpio_port;
  uint16_t gpio_pin;

  GPIO_PinState raw_state;
  GPIO_PinState stable_state;
  uint32_t last_raw_change_ms;
  uint32_t count;
} EncoderChannel;

static EncoderChannel left_encoder;
static EncoderChannel right_encoder;

static void EncoderChannel_Init(EncoderChannel *encoder,
    GPIO_TypeDef *gpio_port, uint16_t gpio_pin, uint32_t now_ms)
{
  GPIO_PinState initial_state = HAL_GPIO_ReadPin(gpio_port, gpio_pin);

  encoder->gpio_port = gpio_port;
  encoder->gpio_pin = gpio_pin;
  encoder->raw_state = initial_state;
  encoder->stable_state = initial_state;
  encoder->last_raw_change_ms = now_ms;
  encoder->count = 0U;
}

static void EncoderChannel_Update(EncoderChannel *encoder, uint32_t now_ms)
{
  GPIO_PinState current_raw_state;

  current_raw_state = HAL_GPIO_ReadPin(encoder->gpio_port, encoder->gpio_pin);

  /*
   * First track raw electrical changes.  A raw change is not trusted yet; it
   * only starts/restarts the debounce timer.
   */
  if (current_raw_state != encoder->raw_state)
  {
    encoder->raw_state = current_raw_state;
    encoder->last_raw_change_ms = now_ms;
  }

  /*
   * Accept the raw level only after it has stayed unchanged for the debounce
   * time.  This rejects fast HIGH/LOW/HIGH chatter around one physical slit.
   */
  if ((encoder->stable_state != encoder->raw_state) &&
      ((now_ms - encoder->last_raw_change_ms) >= ENCODER_DEBOUNCE_MS))
  {
    encoder->stable_state = encoder->raw_state;

    /* Count one pulse per accepted rising edge, same as the Arduino sketch. */
    if (encoder->stable_state == GPIO_PIN_SET)
    {
      encoder->count++;
    }
  }
}

void Encoder_Init(TIM_HandleTypeDef *left_timer, TIM_HandleTypeDef *right_timer)
{
  uint32_t now_ms = HAL_GetTick();

  /*
   * These parameters are intentionally unused in the GPIO-polling test path.
   * They are kept only so main.c can still call Encoder_Init(&htim4, &htim1).
   */
  (void)left_timer;
  (void)right_timer;

  EncoderChannel_Init(&left_encoder, GPIOB, GPIO_PIN_6, now_ms);
  EncoderChannel_Init(&right_encoder, GPIOA, GPIO_PIN_8, now_ms);
}

void Encoder_Update(void)
{
  uint32_t now_ms = HAL_GetTick();

  EncoderChannel_Update(&left_encoder, now_ms);
  EncoderChannel_Update(&right_encoder, now_ms);
}

uint32_t Encoder_GetLeftCount(void)
{
  return left_encoder.count;
}

uint32_t Encoder_GetRightCount(void)
{
  return right_encoder.count;
}

void Encoder_ResetCounts(void)
{
  uint32_t interrupt_state = __get_PRIMASK();

  /*
   * Keep this reset atomic.  Even though this GPIO-polling version increments
   * from the main loop, preserving atomic reset makes this module safe if we
   * later return to interrupt-based counting.
   */
  __disable_irq();
  left_encoder.count = 0U;
  right_encoder.count = 0U;

  /* Preserve the caller's prior interrupt state instead of always enabling it. */
  if (interrupt_state == 0U)
  {
    __enable_irq();
  }
}
