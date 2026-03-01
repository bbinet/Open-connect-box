/**
 * @file usbd_desc.h
 * @brief Header for usbd_desc.c file
 */

#ifndef __USBD_DESC__C__
#define __USBD_DESC__C__

#ifdef __cplusplus
extern "C" {
#endif

/* Includes */
#include "usbd_def.h"

/* Defines */
#define DEVICE_ID1          (0x1FFF7A10)
#define DEVICE_ID2          (0x1FFF7A14)
#define DEVICE_ID3          (0x1FFF7A18)

#define USB_SIZ_STRING_SERIAL       0x1A

/* Exported variables */
extern USBD_DescriptorsTypeDef FS_Desc;

#ifdef __cplusplus
}
#endif

#endif /* __USBD_DESC__C__ */
