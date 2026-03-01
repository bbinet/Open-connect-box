/**
 * @file main.h
 * @brief Header for main.c file
 */

#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes */
#include "stm32f4xx_hal.h"
#include <string.h>

/* Exported types */
extern UART_HandleTypeDef huart1;
extern uint8_t rx_uart_buffer[10];

/* Exported functions prototypes */
void Error_Handler(void);
void USB_CDC_RxHandler(uint8_t *Buf, uint32_t Len);

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
