/*
 * Copyright (c) 2026 HPMicro
 * SPDX-License-Identifier: BSD-3-Clause
 */

#ifndef HPM_PINMUX_H
#define HPM_PINMUX_H

#ifdef __cplusplus
extern "C" {
#endif

void init_uart0_pins(void);
void init_led_pins_as_gpio(void);

#ifdef __cplusplus
}
#endif
#endif /* HPM_PINMUX_H */
