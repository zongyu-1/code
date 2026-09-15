/*
 * Copyright (c) 2026 HPMicro
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include "pinmux.h"
#include "board.h"

/* Debug 串口：UART0 使用 PA00(TXD) / PA01(RXD) */
void init_uart0_pins(void)
{
    HPM_IOC->PAD[IOC_PAD_PA00].FUNC_CTL = IOC_PA00_FUNC_CTL_UART0_TXD;

    HPM_IOC->PAD[IOC_PAD_PA01].FUNC_CTL = IOC_PA01_FUNC_CTL_UART0_RXD;
}

/* LED 指示灯：PC22 复用为 GPIO */
void init_led_pins_as_gpio(void)
{
    HPM_IOC->PAD[IOC_PAD_PC22].FUNC_CTL = IOC_PC22_FUNC_CTL_GPIO_C_22;
}
