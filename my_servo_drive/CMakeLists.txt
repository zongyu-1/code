cmake_minimum_required(VERSION 3.13)

# 1. 【注入硬件防线】告诉 CMake 去你的 boards 目录下找硬件配置
set(BOARD_SEARCH_PATH ${CMAKE_CURRENT_SOURCE_DIR}/boards)
# 默认锁定为你自己建立的底板文件夹名称，以后命令行就不用敲 -DBOARD 了
set(BOARD HPM6E6Y CACHE STRING "Target board name")

# 2. 引入先辑原厂 SDK 底座
find_package(hpm-sdk REQUIRED HINTS $ENV{HPM_SDK_BASE})

# 3. 定义你的项目名称
project(servo_drive_firmware)

# 4. 引入底层 CBB 模块 (motor_hal)
# 注意：如果此时 motor_hal 里完全是空的，这行会报错。
# 请先在 components/motor_hal 下建立下面第 2 步的 CMakeLists.txt
add_subdirectory(components/motor_hal)

# 5. 引入业务层逻辑
add_subdirectory(app)

# 6. 【关键】统一生成工程：必须放在所有子目录添加完毕的最后一行
generate_ide_projects()
