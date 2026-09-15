#include "board.h"
#include "hpm_gpio_drv.h"
#include "hpm_clock_drv.h"
#include "hpm_pllctlv2_drv.h"
#include "hpm_sysctl_drv.h"

int main(void)
{
    /* 板上使用外部 DCDC，board_init() 会调用 board_init_clock() -> pcfg_dcdc_set_voltage()
     * 而内部 DCDC 电感未贴，会卡在 pcfg_dcdc_is_stable() 死循环。
     * 因此这里手动初始化时钟并跳过 DCDC 设置。 */
    uint32_t cpu0_freq = clock_get_frequency(clock_cpu0);
    if (cpu0_freq == PLLCTL_SOC_PLL_REFCLK_FREQ) {
        pllctlv2_xtal_set_rampup_time(HPM_PLLCTLV2, 32ul * 1000ul * 9u);
        sysctl_clock_set_preset(HPM_SYSCTL, 2);
    }
    clock_connect_group_to_cpu(0, 0);

    /* GPIO 模块时钟必须使能，否则所有 GPIO 寄存器写入静默失败 */
    clock_add_to_group(clock_gpio, 0);
    clock_update_core_clock();

    board_init_pmp();
    board_init_console();

    /* 将 PC22 复用为 GPIO，并配置为推挽输出 */
    init_led_pins_as_gpio();
    gpio_set_pin_output(BOARD_LED_GPIO_CTRL, BOARD_LED_GPIO_INDEX, BOARD_LED_GPIO_PIN);

    printf("=== LED Blink on %s, CPU=%luHz ===\n",
           BOARD_LED_GPIO_NAME, clock_get_frequency(clock_cpu0));

    while (1) {
        gpio_toggle_pin(BOARD_LED_GPIO_CTRL, BOARD_LED_GPIO_INDEX, BOARD_LED_GPIO_PIN);
        board_delay_ms(500);
    }

    return 0;
}
