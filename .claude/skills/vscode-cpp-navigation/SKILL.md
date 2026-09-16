---
name: vscode-cpp-navigation
description: 修复 VS Code 中 C/C++ 代码跳转与 IntelliSense 失效的问题 —— 用 CMake 生成 compile_commands.json,再让 cpptools 使用它。适用于符号无法跳转、函数定义找不到、头文件标红、"cannot open source file"、跳转到错误位置、悬停不显示类型等场景,尤其是 CMake + 外部 SDK 的嵌入式项目(如 HPMicro HPM SDK / RISC-V)。当用户说"函数没法跳转""跳不过去""IntelliSense 不工作""头文件找不到""代码标红"时使用。
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# VS Code C/C++ 代码跳转修复

让 IntelliSense 拿到**每个源文件真实的**头文件路径和编译宏,从而能正确解析符号。

## 何时使用

- 有一部分函数能跳转、另一部分跳不了(典型:项目自己的代码能跳,SDK 里的跳不了)
- 头文件下划波浪线报 `cannot open source file`
- 悬停看不到类型、`F12` 无反应或跳到错的位置
- 刚 clone 下来的嵌入式项目,`.vscode/` 里是自动生成的模板配置

## 先判断根因

**读取 `.vscode/c_cpp_properties.json`。** 如果长这样,基本可以确诊:

```json
{
  "compilerPath": "D:/GW/mingw64/bin/gcc.exe",   // 主机编译器,不是目标工具链
  "includePath": ["${workspaceFolder}/**"],       // 只有递归通配,没有 SDK 路径
  "compilerArgs": [""]                            // 空参数
}
```

这是 **C/C++ Runner 扩展自动生成的模板**。它假设项目用主机编译器、不依赖外部 SDK,对嵌入式交叉编译项目完全无效 —— `includePath` 通配符找不到 SDK 头文件(`arch/`、`drivers/`、`soc/`),更不会带上那几十个 `-D` 宏。

判据:项目 `CMakeLists.txt` 里有 `find_package(<某 SDK>)` 或引用外部 SDK 路径,而配置里没有任何指向它的条目。

**不要**试图手工把 SDK 的头文件路径一个个填进 `includePath`。SDK 的宏定义集合庞大且随 SOC 变体变化,手填必然漏。要走下面的编译数据库方案。

## 步骤

### 1. 让 CMake 导出编译数据库

确认项目 `CMakeLists.txt` 里有(通常在 `project()` 之后):

```cmake
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
```

然后**在能通过 `find_package` 找到 SDK 的环境里**配置一次(通常需要 SDK 的环境变量,见"本机具体参数"一节):

```bash
cmake -B build -G Ninja -D<项目参数>
```

产物是 `<build_dir>/compile_commands.json` —— 记录了每个源文件编译时的完整 `-I` 路径和 `-D` 宏。

如果项目用 Ninja 之外的生成器也无妨,`CMAKE_EXPORT_COMPILE_COMMANDS` 对 Ninja 和 Makefile 都有效。

### 2. 写 `.vscode/c_cpp_properties.json`

**整个替换**,关键是 `compileCommands`:

```json
{
  "version": 4,
  "configurations": [
    {
      "name": "<项目名>-<架构>",
      "compileCommands": "${workspaceFolder}/<相对路径>/build/compile_commands.json",
      "compilerPath": "<目标工具链>/bin/<triple>-gcc.exe",
      "cStandard": "gnu17",
      "cppStandard": "gnu++17",
      "includePath": [
        "${workspaceFolder}/<项目目录>/**",
        "<SDK 根目录>/**"
      ],
      "browse": {
        "path": ["${workspaceFolder}/<项目目录>", "<SDK 根目录>"],
        "limitSymbolsToIncludedHeaders": false
      }
    }
  ]
}
```

- `compileCommands` 是主力:对每个源文件用 DB 里那份真实参数。
- `compilerPath` 让 cpptools 查询**目标编译器**的内置宏(如 `__riscv`),而不是主机 gcc 的。
- `includePath` + `browse.path` 是兜底,用于 DB 里没有的文件(比如直接打开的 SDK 头文件)。

### 3. 写 `.vscode/settings.json`

**先删掉所有 `C_Cpp_Runner.*` 开头的设置。** 这些是模板残留,会把编译器指回主机 `gcc`/`g++`/`gdb`,持续干扰 IntelliSense。

再补上 CMake Tools 配置,方便日后重新生成 DB:

```json
{
  "cmake.sourceDirectory": "${workspaceFolder}/<项目目录>",
  "cmake.buildDirectory": "${sourceDirectory}/build",
  "cmake.generator": "Ninja",
  "cmake.cmakePath": "<cmake 可执行文件绝对路径>",
  "cmake.configureSettings": { "...": "..." },
  "cmake.configureEnvironment": {
    "<SDK 环境变量>": "...",
    "PATH": "<工具链 bin>;${env:PATH}"
  },
  "C_Cpp.default.compileCommands": "${workspaceFolder}/<相对路径>/build/compile_commands.json",
  "C_Cpp.default.compilerPath": "<目标工具链>/bin/<triple>-gcc.exe"
}
```

`cmake.cmakePath` 和 `cmake.configureEnvironment` 只在 **cmake / ninja / 工具链不在系统 PATH 上**时才需要。先跑 `which cmake ninja` 确认;如果命令解析不到,就显式指定。

### 4. 验证(必做)

不要跳过这步 —— 配置写对和 IntelliSense 真能解析是两回事。

```bash
python .claude/skills/vscode-cpp-navigation/scripts/verify_compile_db.py <build_dir>/compile_commands.json
```

脚本会校验 DB 里每个 `-I` 目录和源文件是否真实存在,并用某个源文件的原始参数跑一次 `-fsyntax-only`。

**判据:退出码 0 且无诊断输出**,说明头文件和宏全部解析成功,IntelliSense 用的是同一套参数。

### 5. 让用户重载窗口

告诉用户执行 `Ctrl+Shift+P` → `Developer: Reload Window`。设置类配置不会热生效。

## 本机具体参数(HPMSDK / HPM6E6Y)

本机 `cmake`、`ninja`、RISC-V 工具链**都不在系统 PATH 上**(PATH 里的 `E:\STM32CUBECLT\...` 是失效路径)。全部来自 SDK 环境包:

| 用途 | 路径 |
|---|---|
| SDK | `F:\HPM\sdk_env\hpm_sdk` |
| 工具链 | `F:\HPM\sdk_env\toolchains\rv32imac_zicsr_zifencei_multilib_b_ext-win` |
| cmake 3.24 | `F:\HPM\sdk_env\tools\cmake\bin\cmake.exe` |
| ninja | `F:\HPM\sdk_env\tools\ninja\ninja.exe` |

环境变量:`HPM_SDK_BASE` 已是持久化用户环境变量;**`GNURISCV_TOOLCHAIN_PATH` 没有持久化**,SDK 缺它会直接 `FATAL_ERROR`。

从 SDK 环境的干净 shell 里生成 DB:

```bash
export HPM_SDK_BASE="F:/HPM/sdk_env/hpm_sdk" && export GNURISCV_TOOLCHAIN_PATH="F:/HPM/sdk_env/toolchains/rv32imac_zicsr_zifencei_multilib_b_ext-win" && export PATH="/f/HPM/sdk_env/tools/cmake/bin:/f/HPM/sdk_env/tools/ninja:$PATH" && cd "F:/servo-drive-HPM6E6Y/my_servo_drive" && cmake -B build -G Ninja -DBOARD=HPM6E6Y -DHPM_BUILD_TYPE=ram -DCMAKE_BUILD_TYPE=debug
```

HPM SDK 1.10 的构建类型:`ram`(默认)、`flash_xip`(额外定义 `FLASH_XIP=1`)、`flash_sdram_xip` 等。**选哪个会影响 `FLASH_XIP` 相关的条件编译分支**,所以要跟用户实际的烧录方式一致。

## 陷阱

- **`compile_commands.json` 绝对不能提交进仓库。** 里面是绝对路径(指向本机 SDK 和工具链安装位置),别人机器上全断。而且它通常在 `build/` 下,已被 `.gitignore` 覆盖。每台机器各自生成。
- **cpptools 没有 RISC-V 的 `intelliSenseMode`。** 可选值只有 x86 / ARM 系列。显式指定 `linux-gcc-arm` 之类会注入**错误的架构内置宏**。正确做法是省略该字段(或写 `${default}`),让 cpptools 从 `compilerPath` 查询目标编译器。
- **不要漏掉删 `C_Cpp_Runner.*`。** 只改 `c_cpp_properties.json` 而不清理 `settings.json`,残留设置仍可能把工具链指回主机。
- **DB 只覆盖被编译的源文件。** 如果一个 `.c` 没被任何 CMake 目标引用,它就不在 DB 里,IntelliSense 会退回 `includePath`/`browse.path`。遇到"只有某个文件不能跳",先查它是否真的参与了构建。
- **改构建配置后 DB 会过期。** 新增源文件、增删 `target_link_libraries`、切换构建类型后,都要重新 configure。

## 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| 跳转完全没反应 | `compileCommands` 路径写错,或 DB 不存在 | 用 Read 确认文件真的在该路径 |
| 只有 SDK 函数跳不了 | `compilerPath` 或 `includePath` 没指到 SDK | 跑验证脚本,看 `-I` 是否有缺失 |
| 大面积为红波浪线 | 缺 `-D` 宏 —— 多半用了错的构建类型 | 改用与烧录方式一致的 `HPM_BUILD_TYPE` 重新 configure |
| 架构宏错误(如出现 `__ARM_ARCH`) | 显式设了不匹配的 `intelliSenseMode` | 改为 `${default}` 或删掉该字段 |
| 改了配置没反应 | 设置未热重载 | `Developer: Reload Window` |
| CMake 面板报 `cmake not found` | cmake 不在 PATH | 设 `cmake.cmakePath` 指向 SDK 自带那份 |
