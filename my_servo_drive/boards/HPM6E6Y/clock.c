/*
 * Copyright (c) 2026 HPMicro
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include "clock.h"
#include "hpm_soc.h"
#include "hpm_clock_drv.h"

/* Debug 串口使用的 UART0 时钟使能，被 board_init_console() 调用 */
void init_uart0_clock(void)
{
    clock_add_to_group(clock_uart0, 0);
}
