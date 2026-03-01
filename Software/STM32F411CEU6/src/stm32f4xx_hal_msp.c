/**
 * @file stm32f4xx_hal_msp.c
 * @brief MSP Initialization and de-Initialization callbacks
 */

#include "main.h"

/**
 * @brief  Initializes the Global MSP.
 * @retval None
 */
void HAL_MspInit(void)
{
    __HAL_RCC_SYSCFG_CLK_ENABLE();
    __HAL_RCC_PWR_CLK_ENABLE();
}

/**
 * @brief UART MSP Initialization
 *        This function configures the hardware resources used for UART:
 *        - Peripheral's clock enable
 *        - GPIO configuration
 * @param huart: UART handle pointer
 * @retval None
 */
void HAL_UART_MspInit(UART_HandleTypeDef *huart)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    if (huart->Instance == USART1)
    {
        /* Peripheral clock enable */
        __HAL_RCC_USART1_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /**
         * USART1 GPIO Configuration
         * PA9  ------> USART1_TX
         * PA10 ------> USART1_RX
         */
        GPIO_InitStruct.Pin = GPIO_PIN_9 | GPIO_PIN_10;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Pull = GPIO_NOPULL;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
        GPIO_InitStruct.Alternate = GPIO_AF7_USART1;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
    }
}

/**
 * @brief UART MSP De-Initialization
 * @param huart: UART handle pointer
 * @retval None
 */
void HAL_UART_MspDeInit(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        /* Peripheral clock disable */
        __HAL_RCC_USART1_CLK_DISABLE();

        /* USART1 GPIO Configuration */
        HAL_GPIO_DeInit(GPIOA, GPIO_PIN_9 | GPIO_PIN_10);
    }
}

/**
 * @brief PCD (USB) MSP Initialization
 *        This function configures the hardware resources used for USB:
 *        - Peripheral's clock enable
 *        - GPIO configuration
 *        - NVIC configuration
 * @param hpcd: PCD handle pointer
 * @retval None
 */
void HAL_PCD_MspInit(PCD_HandleTypeDef *hpcd)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    if (hpcd->Instance == USB_OTG_FS)
    {
        /* Enable GPIO clock */
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /**
         * USB_OTG_FS GPIO Configuration
         * PA11 ------> USB_OTG_FS_DM
         * PA12 ------> USB_OTG_FS_DP
         */
        GPIO_InitStruct.Pin = GPIO_PIN_11 | GPIO_PIN_12;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Pull = GPIO_NOPULL;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
        GPIO_InitStruct.Alternate = GPIO_AF10_OTG_FS;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

        /* Enable USB clock */
        __HAL_RCC_USB_OTG_FS_CLK_ENABLE();

        /* Enable SYSCFG clock */
        __HAL_RCC_SYSCFG_CLK_ENABLE();

        /* USB_OTG_FS interrupt Init */
        HAL_NVIC_SetPriority(OTG_FS_IRQn, 0, 0);
        HAL_NVIC_EnableIRQ(OTG_FS_IRQn);
    }
}

/**
 * @brief PCD (USB) MSP De-Initialization
 * @param hpcd: PCD handle pointer
 * @retval None
 */
void HAL_PCD_MspDeInit(PCD_HandleTypeDef *hpcd)
{
    if (hpcd->Instance == USB_OTG_FS)
    {
        /* Disable peripheral clock */
        __HAL_RCC_USB_OTG_FS_CLK_DISABLE();

        /* USB_OTG_FS GPIO Configuration */
        HAL_GPIO_DeInit(GPIOA, GPIO_PIN_11 | GPIO_PIN_12);

        /* USB_OTG_FS interrupt DeInit */
        HAL_NVIC_DisableIRQ(OTG_FS_IRQn);
    }
}
