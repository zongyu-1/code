# 将 motor_hal 声明为一个静态库 (Static Library)
add_library(motor_hal STATIC)

# 声明你的源文件 (你需要新建一个空的 src/motor_hal.c 占位，否则 CMake 会报错)
target_sources(motor_hal PRIVATE
    src/motor_hal.c
)

# 暴露你的头文件目录给 app 层使用
# target_include_directories(motor_hal PUBLIC inc) <-- 等你建好 inc/motor_hal.h 后取消注释

# 链接原厂 SDK 的底层驱动（你需要什么外设，就在这里按需向原厂“进货”）
# target_link_libraries(motor_hal PUBLIC hpm_pwm hpm_gpio hpm_qei)
