---
name: hpm-flash-jlink
description: 通过 J-Link 探针把固件烧录/加载到 HPMicro HPM6E6Y(SoC HPM6E80)板,以及 JLink Commander 一连串会静默失败的陷阱。当用户说"烧录""下载程序""下载固件""烧到板子""flash""JLink 一下",或说已连接芯片要求下载时使用。也用于排查 openocd 报 LIBUSB_ERROR_NOT_SUPPORTED / No J-Link device found、或"烧录命令返回成功但固件没变"的问题。
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# 用 J-Link 烧录 HPM6E6Y

这块板子只能走 **J-Link 探针**。下面每个陷阱都是实际踩过的——尤其是第 2 条,它会让烧录**看起来成功但实际什么都没写**。

## 开烧之前

1. **确认固件已构建**。`my_servo_drive/build/output/demo.elf` 必须存在且是新的。
   `build/output/` 是空的说明只跑过 CMake 配置、没跑过编译 —— 先 `cmake --build build`。

2. **确认电机功率级没上电**。这是伺服驱动器,不是普通开发板。

3. **确认构建类型**。默认 `ram` 构建链接到片内 ILM/DLM,**断电即失效**;要断电保持必须用 `flash_xip` 重建再写 QSPI Flash。用 readelf 看入口和段就能判断:

   ```bash
   riscv32-unknown-elf-readelf -h -l build/output/demo.elf
   ```

   `ram`:入口 `0x0`,段落在 `0x00000000`/`0x01200000`。此时 `setpc 0x00000000` 正确。

## 陷阱清单

### 1. openocd 驱动不了 J-Link(别在这上面浪费时间)

SDK 自带 openocd 和完整配置(`hpm_sdk/boards/openocd/soc/hpm6e80-single-core.cfg` + `probes/jlink.cfg`),但**用不了**:

```
Warn : Failed to open device: LIBUSB_ERROR_NOT_SUPPORTED
Error: No J-Link device found
```

原因:openocd 的 J-Link 支持走 libusb,而 libusb 在 Windows 上只能操作绑定 **WinUSB** 的设备。J-Link 探针绑的是 SEGGER 私有驱动。用 `Get-PnpDevice` 看,`Class` 是 `USB` 而不是 `WinUSB`,`FriendlyName` 是 `J-Link driver`,驱动提供者是 `Segger`。

**改用 `JLink.exe`,不要用 Zadig 换驱动。** 换 WinUSB 虽能让 openocd 工作,但会破坏 SEGGER 驱动,JLink.exe 和 cortex-debug 调试就都不能用了。

### 2. `connect` 之后必须跟一个空行(吞命令的根因)

这是所有诡异现象的根源。J-Link 在 `connect` 之后**会吞掉紧接着的那一行**,因为它要拿那行去回答一个 JTAG 链位置提示:

```
Device position in JTAG chain (IRPre,DRPre) <Default>: -1,-1 => Auto-detect
```

要命的是**这个提示有时根本不显示**。于是那一行命令就悄无声息地消失,而 JLink 看上去一切正常。实测中 `loadfile` 和 `savebin` 都这样丢过,表现为"命令没执行"或"文件没生成"。

**修法:在 `connect` 后面加一个空行。**

```
connect
              <-- 空行,吸收提示
loadfile ...
```

提示不出现时空行会被无害忽略,出现时正好被它吃掉。加上这一行之后,行为从时灵时不灵变成稳定成功。

### 3. 别用 `-CommanderScript`

同样的吞行问题在脚本模式下更致命:提示会把**脚本后续的命令全部**当成回答吃掉。

```
JLink.exe -CommanderScript _flash.jlink     # 不要这样用
```

固件根本没下载,但 JLink 照样打印 "Script processing completed" 并**返回退出码 0**。`-ExitOnError 1` 也拦不住。

**改用 stdin 管道**,并强制检查输出里是否真的出现下载成功标志:

```
Downloading file [.../demo.elf]...
O.K.
```

只有这一处能证明固件被写入,**退出码不可信**。

### 4. `halt` 在这块探针上不可靠

`halt` 之后 `regs` 报 `CPU is not halted !`。日志里有警告:

```
RISC-V: The connected J-Link (S/N ...) uses an old firmware module V1 with known problems / limitations.
```

**不要靠 halt 读 PC 来验证。** 后台内存访问是通的(`BG memory access support: Via SBA`),用 `savebin` 采样内存来验证(见下)。

### 5. 设备名大小写不敏感,但别猜

J-Link 设备库里是 `HPM6E6YxGNx`(小写 `x` 占位),而 `_flash.jlink` 里写的是 `HPM6E6YXGNX`(全大写),**实测能连上**,说明匹配不区分大小写。

不确定设备名时,直接搜 DLL(DLL 里嵌了设备库,没有独立的 XML):

```bash
grep -a -o 'HPM6E[0-9A-Za-z]\{2,12\}' "G:/jlink/JLink_V960/JLink_x64.dll" | sort -u
```

同系列可用名:`HPM6E60xVMx`、`HPM6E80xVMx`、`HPM6E80xGNx`、`HPM6E8YxVMx` 等。板级 yaml 的 `device:` 字段注释写明了"device name used for jlink connection",可作交叉验证。

### 6. SDK 的 `program_flash.cmd` 对自定义板无效

`tools/scripts/program_flash.cmd` 会去找 `%HPM_SDK_BASE%\boards\<board>\<board>.yaml`。而 `HPM6E6Y` 是本项目里的**自定义板**(在 `my_servo_drive/boards/` 下),不在 SDK 的 boards 目录里,所以脚本只会打印"列出所有板卡"然后退出。直接调 JLink。

## 标准流程

用脚本封装,规避第 2、3 条:

```bash
bash .claude/skills/hpm-flash-jlink/scripts/flash.sh
```

或手动管道(**注意 `connect\n\n` 那个空行**):

```bash
printf 'si 0\nspeed 4000\ndevice HPM6E6YXGNX\nconnect\n\nr\nloadfile <ELF绝对路径>\nsetpc 0x00000000\ng\nqc\n' | "G:/jlink/JLink_V960/JLink.exe"
```

## 验证固件真的在跑

LED 是 **PC22**,GPIO0 基址 `0xF00D0000`,`DO[16]` 数组从 `+0x100` 开始、每组 `0x10` 字节,所以端口 C 的输出寄存器 `DO[2].VALUE` 在 **`0xF00D0120`**,bit 22 即 PC22。

采样几次并比对——`0x00400000` 这一位在变化就说明闪烁循环在跑:

```bash
printf 'si 0\nspeed 4000\ndevice HPM6E6YXGNX\nconnect\n\nsavebin C:/tmp/a.bin 0xF00D0120 4\nsleep 300\nsavebin C:/tmp/b.bin 0xF00D0120 4\nqc\n' | "G:/jlink/JLink_V960/JLink.exe"
```

采样间隔取 300ms 左右、多采几次。LED 是 500ms 翻转,两次采样落在同一半周期拿到相同值是正常的,别据此判失败。`flash.sh` 已内置这步验证。

## 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `No J-Link device found` | 用 openocd 而非 JLink.exe | 见陷阱 1 |
| 退出码 0 但固件没更新 | `-CommanderScript` 吞掉了后续全部命令 | 陷阱 3,改用管道 |
| 某条命令莫名没生效 | `connect` 后缺空行,那一行被提示吞了 | 陷阱 2,加空行 |
| `CPU is not halted !` | 探针固件老旧 | 见陷阱 4,改用 savebin 验证 |
| `Unknown device` | 设备名不对 | 任务 5 的 grep 命令查真实名字 |
| `program_flash.cmd` 列出全部板卡 | 自定义板不在 SDK boards 下 | 见陷阱 6,直接调 JLink |

## 本机参数

| 用途 | 值 |
|---|---|
| JLink.exe | `G:\jlink\JLink_V960\JLink.exe`(**不在** `C:\Program Files\SEGGER`) |
| 探针 | J-Link Pro V4,S/N 601012541 |
| USB 驱动 | Segger 2.70.8.0(`oem69.inf`,Class USB — 非 WinUSB) |
| 设备名 | `HPM6E6YXGNX` |
| 固件 | `F:\servo-drive-HPM6E6Y\my_servo_drive\build\output\demo.elf` |
| 工具链 readelf | `F:\HPM\sdk_env\toolchains\rv32imac_zicsr_zifencei_multilib_b_ext-win\bin\riscv32-unknown-elf-readelf.exe` |
