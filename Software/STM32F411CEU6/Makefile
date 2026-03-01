#######################################
# Makefile for STM32F411CEU6 USB-UART Bridge
#######################################

######################################
# Target
######################################
TARGET = blackpill_F411CEU6

######################################
# Building variables
######################################
DEBUG = 1
OPT = -Os

#######################################
# Paths
#######################################
BUILD_DIR = build
HAL_DIR = Drivers/STM32F4xx_HAL_Driver
USB_DIR = Middlewares/ST/STM32_USB_Device_Library

######################################
# Source files
######################################
# C sources
C_SOURCES = \
src/main.c \
src/stm32f4xx_hal_msp.c \
src/stm32f4xx_it.c \
src/system_stm32f4xx.c \
src/usb_device.c \
src/usbd_conf.c \
src/usbd_desc.c \
src/usbd_cdc_if.c \
$(HAL_DIR)/Src/stm32f4xx_hal.c \
$(HAL_DIR)/Src/stm32f4xx_hal_cortex.c \
$(HAL_DIR)/Src/stm32f4xx_hal_gpio.c \
$(HAL_DIR)/Src/stm32f4xx_hal_rcc.c \
$(HAL_DIR)/Src/stm32f4xx_hal_rcc_ex.c \
$(HAL_DIR)/Src/stm32f4xx_hal_pwr.c \
$(HAL_DIR)/Src/stm32f4xx_hal_pwr_ex.c \
$(HAL_DIR)/Src/stm32f4xx_hal_uart.c \
$(HAL_DIR)/Src/stm32f4xx_hal_pcd.c \
$(HAL_DIR)/Src/stm32f4xx_hal_pcd_ex.c \
$(HAL_DIR)/Src/stm32f4xx_ll_usb.c \
$(HAL_DIR)/Src/stm32f4xx_hal_flash.c \
$(HAL_DIR)/Src/stm32f4xx_hal_flash_ex.c \
$(HAL_DIR)/Src/stm32f4xx_hal_dma.c \
$(USB_DIR)/Core/Src/usbd_core.c \
$(USB_DIR)/Core/Src/usbd_ctlreq.c \
$(USB_DIR)/Core/Src/usbd_ioreq.c \
$(USB_DIR)/Class/CDC/Src/usbd_cdc.c

# ASM sources
ASM_SOURCES = \
src/startup_stm32f411ceux.s

#######################################
# Binaries
#######################################
PREFIX = arm-none-eabi-
CC = $(PREFIX)gcc
AS = $(PREFIX)gcc -x assembler-with-cpp
CP = $(PREFIX)objcopy
SZ = $(PREFIX)size
HEX = $(CP) -O ihex
BIN = $(CP) -O binary -S

#######################################
# CFLAGS
#######################################
CPU = -mcpu=cortex-m4
FPU = -mfpu=fpv4-sp-d16
FLOAT-ABI = -mfloat-abi=hard
MCU = $(CPU) -mthumb $(FPU) $(FLOAT-ABI)

# macros for gcc
AS_DEFS =

C_DEFS = \
-DUSE_HAL_DRIVER \
-DSTM32F411xE \
-DHSE_VALUE=25000000

# includes
C_INCLUDES = \
-Isrc \
-IInc \
-I$(HAL_DIR)/Inc \
-I$(HAL_DIR)/Inc/Legacy \
-IDrivers/CMSIS/Device/ST/STM32F4xx/Include \
-IDrivers/CMSIS/Core/Include \
-I$(USB_DIR)/Core/Inc \
-I$(USB_DIR)/Class/CDC/Inc

ASFLAGS = $(MCU) $(AS_DEFS) $(OPT) -Wall -fdata-sections -ffunction-sections

CFLAGS = $(MCU) $(C_DEFS) $(C_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections

ifeq ($(DEBUG), 1)
CFLAGS += -g -gdwarf-2
endif

CFLAGS += -MMD -MP -MF"$(@:%.o=%.d)"

#######################################
# LDFLAGS
#######################################
LDSCRIPT = STM32F411CEUX_FLASH.ld

LIBS = -lc -lm -lnosys
LIBDIR =
LDFLAGS = $(MCU) -specs=nano.specs -T$(LDSCRIPT) $(LIBDIR) $(LIBS) -Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref -Wl,--gc-sections

#######################################
# Build targets
#######################################
# Default target
all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin

# Simple compile alias
.PHONY: all clean flash

OBJECTS = $(addprefix $(BUILD_DIR)/,$(notdir $(C_SOURCES:.c=.o)))
vpath %.c $(sort $(dir $(C_SOURCES)))

OBJECTS += $(addprefix $(BUILD_DIR)/,$(notdir $(ASM_SOURCES:.s=.o)))
vpath %.s $(sort $(dir $(ASM_SOURCES)))

$(BUILD_DIR)/%.o: %.c Makefile | $(BUILD_DIR)
	$(CC) -c $(CFLAGS) -Wa,-a,-ad,-alms=$(BUILD_DIR)/$(notdir $(<:.c=.lst)) $< -o $@

$(BUILD_DIR)/%.o: %.s Makefile | $(BUILD_DIR)
	$(AS) -c $(ASFLAGS) $< -o $@

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS) Makefile
	$(CC) $(OBJECTS) $(LDFLAGS) -o $@
	$(SZ) $@

$(BUILD_DIR)/%.hex: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
	$(HEX) $< $@

$(BUILD_DIR)/%.bin: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
	$(BIN) $< $@

$(BUILD_DIR):
	mkdir $@

#######################################
# Clean
#######################################
clean:
	-rm -fR $(BUILD_DIR)

#######################################
# Flash with DFU
#######################################
flash: $(BUILD_DIR)/$(TARGET).bin
	dfu-util -a 0 -d 0483:df11 -S 379536673235 -s 0x08000000:leave -D $<

#######################################
# Dependencies
#######################################
-include $(wildcard $(BUILD_DIR)/*.d)
