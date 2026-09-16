#!/usr/bin/env python3
"""校验 CMake 导出的 compile_commands.json 是否真的可用。

检查三件事:
  1. 每条记录里的 -I / -isystem 头文件目录是否真实存在
  2. 每个源文件是否真实存在
  3. 用某条记录的原始参数跑一次 -fsyntax-only,确认头文件和宏都能解析

用法:
    python verify_compile_db.py <path/to/compile_commands.json> [选项]

选项:
    --check <FILE>   指定要用原始参数语法检查的源文件(默认取第一条记录)
    --no-check       只做路径校验,跳过语法检查
    -q, --quiet      只输出结论

退出码:
    0  全部通过
    1  存在缺失路径或语法检查失败
    2  参数/文件错误
"""

import argparse
import json
import os
import shlex
import subprocess
import sys


def split_command(command, directory):
    """把命令行拆成 token 列表,并把 Windows 反斜杠统一成正斜杠。"""
    normalized = command.replace("\\", "/")
    return shlex.split(normalized, posix=True)


def extract_include_dirs(tokens, directory):
    """从 token 列表里抽出 -I / -isystem 的头文件目录,解析为绝对路径。"""
    dirs = []
    take_next = False
    for token in tokens:
        if take_next:
            dirs.append(token)
            take_next = False
            continue
        if token == "-I" or token == "-isystem":
            take_next = True
        elif token.startswith("-I") and len(token) > 2:
            dirs.append(token[2:])
        elif token.startswith("-isystem") and len(token) > len("-isystem"):
            dirs.append(token[len("-isystem"):])

    resolved = []
    for d in dirs:
        d = d.rstrip("/")
        if not d:
            continue
        resolved.append(d if os.path.isabs(d) else os.path.normpath(os.path.join(directory, d)))
    return resolved


def build_syntax_check_args(entry):
    """把一条编译记录改造成 -fsyntax-only 调用,返回 (argv, source_path)。"""
    tokens = split_command(entry["command"], entry.get("directory", "."))
    source = entry["file"].replace("\\", "/")

    argv = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token == "-o":          # 丢弃输出目标
            skip_next = True
            continue
        if token in ("-c", "--compile"):  # 交给 -fsyntax-only
            continue
        if token == source or os.path.normpath(token) == os.path.normpath(source):
            continue
        argv.append(token)

    argv += ["-fsyntax-only", source]
    return argv, source


def main():
    # Windows 控制台默认按 GBK 编码输出,而终端多数期望 UTF-8,中文会乱码
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="校验 compile_commands.json 可用性")
    parser.add_argument("db", help="compile_commands.json 路径")
    parser.add_argument("--check", metavar="FILE", help="用原始参数语法检查指定源文件")
    parser.add_argument("--no-check", action="store_true", help="跳过语法检查")
    parser.add_argument("-q", "--quiet", action="store_true", help="只输出结论")
    args = parser.parse_args()

    if not os.path.isfile(args.db):
        print("错误: 找不到 %s" % args.db)
        return 2

    try:
        with open(args.db, encoding="utf-8") as fh:
            entries = json.load(fh)
    except (ValueError, OSError) as exc:
        print("错误: 无法解析 %s: %s" % (args.db, exc))
        return 2

    if not entries:
        print("错误: %s 里没有任何编译记录" % args.db)
        return 2

    failures = 0

    # ---- 1 & 2. 路径校验 ----
    checked_dirs = set()
    missing_dirs = set()
    for entry in entries:
        directory = entry.get("directory", ".")
        tokens = split_command(entry["command"], directory)
        for path in extract_include_dirs(tokens, directory):
            if path in checked_dirs:
                continue
            checked_dirs.add(path)
            if not os.path.isdir(path):
                missing_dirs.add(path)

    missing_sources = [e["file"] for e in entries if not os.path.isfile(e["file"])]

    if not args.quiet:
        print("记录数        : %d" % len(entries))
        print("头文件目录    : %d 个,缺失 %d 个" % (len(checked_dirs), len(missing_dirs)))
        print("源文件        : %d 个,缺失 %d 个" % (len(entries), len(missing_sources)))
        for path in sorted(missing_dirs):
            print("    缺失目录: %s" % path)
        for path in sorted(missing_sources):
            print("    缺失文件: %s" % path)

    if missing_dirs or missing_sources:
        failures += 1

    # ---- 3. 语法检查 ----
    if args.no_check:
        if not args.quiet:
            print("\n(已跳过语法检查)")
    else:
        if args.check:
            norm = os.path.normpath(args.check)
            matches = [e for e in entries
                       if os.path.normpath(e["file"]) == norm
                       or os.path.basename(e["file"]) == args.check]
            if not matches:
                print("错误: DB 里没有 %s 的编译记录" % args.check)
                return 2
            entry = matches[0]
        else:
            entry = entries[0]

        argv, source = build_syntax_check_args(entry)
        if not args.quiet:
            print("\n语法检查      : %s" % source)
            print("编译器        : %s" % argv[0])

        try:
            proc = subprocess.run(argv, capture_output=True, text=True)
        except OSError as exc:
            print("错误: 无法执行编译器 %s: %s" % (argv[0], exc))
            return 2

        if proc.returncode == 0:
            if not args.quiet:
                print("结果          : 通过,头文件与宏全部解析成功")
        else:
            failures += 1
            if not args.quiet:
                print("结果          : 失败 (exit %d)" % proc.returncode)
                stderr = (proc.stderr or "").strip()
                for line in stderr.splitlines()[:30]:
                    print("    %s" % line)
                if not stderr:
                    print("    (编译器无 stderr 输出)")

    print()
    if failures:
        print("结论: 有问题,IntelliSense 可能仍然无法正确解析。")
        return 1
    print("结论: 全部通过,IntelliSense 使用的参数有效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
