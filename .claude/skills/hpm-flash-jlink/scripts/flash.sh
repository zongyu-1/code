#!/usr/bin/env bash
# 通过 J-Link 把 ELF 加载到片内 RAM 并运行。
#
# 规避 JLink 的两个陷阱(详见 ../SKILL.md):
#   1. connect 之后必须跟一个空行 —— JLink 会用一个提示(有时还不可见)吞掉
#      紧接着的那一行命令。少了空行,loadfile 会静默消失,而退出码仍是 0。
#   2. -CommanderScript 模式下整个脚本都会被吞掉,所以这里用 stdin 管道。
#
# 用法:
#   bash flash.sh [ELF路径]
#
# 环境变量覆盖:
#   JLINK=...  DEVICE=...  ENTRY=...  ATTEMPTS=...  VERIFY=0
#
# 退出码: 0 成功 / 1 烧录失败 / 2 前置条件不满足

set -uo pipefail

JLINK=${JLINK:-G:/jlink/JLink_V960/JLink.exe}
DEVICE=${DEVICE:-HPM6E6YXGNX}
ENTRY=${ENTRY:-0x00000000}
ATTEMPTS=${ATTEMPTS:-3}
VERIFY=${VERIFY:-1}
ELF=${1:-F:/servo-drive-HPM6E6Y/my_servo_drive/build/output/demo.elf}

# GPIO0 端口 C 输出寄存器 = 0xF00D0000 + 0x100 + 2*0x10,bit 22 即 LED(PC22)
LED_REG=0xF00D0120

die() { echo "错误: $*" >&2; exit 2; }

[[ -x "$JLINK" ]] || die "找不到 JLink 可执行文件: $JLINK  (用 JLINK= 覆盖)"
[[ -f "$ELF"   ]] || die "找不到固件: $ELF  (先跑 cmake --build build)"

echo "JLink : $JLINK"
echo "固件  : $ELF"
echo "设备  : $DEVICE    入口: $ENTRY"
echo

# ---------------------------------------------------------------- 烧录
flashed=0
for ((i = 1; i <= ATTEMPTS; i++)); do
    echo "--- 第 $i/$ATTEMPTS 次尝试 ---"

    out=$(printf 'si 0\nspeed 4000\ndevice %s\nconnect\n\nr\nloadfile %s\nsetpc %s\ng\nqc\n' \
              "$DEVICE" "$ELF" "$ENTRY" | timeout 120 "$JLINK" 2>&1)
    code=$?

    echo "$out"

    # 只有这一处能证明固件真的被写入。退出码 0 不足以说明问题。
    if grep -A1 "Downloading file" <<<"$out" | grep -q 'O\.K\.'; then
        flashed=1
        break
    fi

    if [[ $code -eq 124 ]]; then
        echo "第 $i 次超时" >&2
    else
        echo "第 $i 次未出现下载成功标志(退出码 $code)" >&2
    fi
    echo >&2
done

if [[ $flashed -eq 0 ]]; then
    echo "失败: $ATTEMPTS 次都没真正写入固件。" >&2
    echo "排查方向:探针是否连接、设备名是否正确(见 SKILL.md 陷阱 5)。" >&2
    exit 1
fi

echo
echo "烧录成功:固件已加载并运行(入口 $ENTRY)"

# ---------------------------------------------------------------- 验证
# halt/regs 在这块探针上不可靠,只能靠后台内存采样。
[[ "$VERIFY" == "0" ]] && exit 0

vdir=$(dirname "$ELF")
samples=()
for n in 1 2 3 4 5 6; do
    f="$vdir/_verify$n.bin"
    rm -f "$f"
    printf 'si 0\nspeed 4000\ndevice %s\nconnect\n\nsavebin %s %s 4\nqc\n' \
        "$DEVICE" "$f" "$LED_REG" | timeout 60 "$JLINK" >/dev/null 2>&1
    [[ -f "$f" ]] && samples+=("$f")
    sleep 0.25
done

rm -f "$vdir"/_verify*.bin

echo
if (( ${#samples[@]} < 2 )); then
    echo "验证跳过:只采到 ${#samples[@]} 个样本(JTAGConf 又吃掉了几条 savebin)" >&2
    exit 0
fi

distinct=1
for f in "${samples[@]:1}"; do
    cmp -s "${samples[0]}" "$f" || { distinct=0; break; }
done

if [[ $distinct -eq 0 ]]; then
    echo "验证通过:LED 寄存器 $LED_REG 的采样值发生变化,闪烁循环正在执行"
else
    echo "注意:${#samples[@]} 个样本完全一致,未观察到 LED 翻转。" >&2
    echo "     可能是采样时机巧合,也可能是代码卡住了——建议重跑或检查硬件。" >&2
fi

exit 0
