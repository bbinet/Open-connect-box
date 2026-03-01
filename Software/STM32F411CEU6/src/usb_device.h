/**
 * @file usb_device.h
 * @brief Header for usb_device.c file
 */

#ifndef __USB_DEVICE__H__
#define __USB_DEVICE__H__

#ifdef __cplusplus
extern "C" {
#endif

/* Includes */
#include "stm32f4xx.h"
#include "stm32f4xx_hal.h"
#include "usbd_def.h"

/* Exported variables */
extern USBD_HandleTypeDef hUsbDeviceFS;

/* Exported functions prototypes */
void MX_USB_DEVICE_Init(void);

#ifdef __cplusplus
}
#endif

#endif /* __USB_DEVICE__H__ */
