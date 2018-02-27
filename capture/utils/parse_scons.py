# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_scons.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-02-27 16:32:04
    @LastModif: 2018-02-27 16:32:04
    @Note:
"""

import os
import subprocess
import re
import parse_make

DEFAULT_SCONSTRUCT_NAME = "SConstruct"


def has_file_s(line):
    file_regex = re.compile("(^.+\.c$)|(^.+\.cc$)|(^.+\.cpp$)|(^.+\.cxx$)")
    words = line.strip().split("\t ")
    for w in words:
        if file_regex.match(words):
            return True
    return False


def check_command_format(result, other_cc_compiles=None, other_cxx_compiles=None):
    cc_re_compile_str = "(.*-?g?cc )|(.*-?clang )"
    if other_cc_compiles:
        for cc_compile in other_cc_compiles:
            cc_re_compile_str += "|(.*-?" + cc_compile + ' )'
    cxx_re_compile_str = "(.*-?[gc]\+\+ )|(.*-?clang\+\+ )"
    if other_cxx_compiles:
        for cxx_compile in other_cxx_compiles:
            # Maybe have some problem
            if cxx_compile[-2:] == "++":
                cxx_compile.replace('++', '\\+\\+')
            cxx_re_compile_str += "|(.*-?" + cxx_compile + ' )'
    cc_compile_regex = re.compile(cc_re_compile_str)
    cpp_compile_regex = re.compile(cxx_re_compile_str)
    for line in result.split("\n"):
        if (cc_compile_regex.match(line) or cpp_compile_regex.match(line)) \
                and has_file_s(line):
            return True
        else:
            continue
    return False


# 使用 make -Bnkw 方式获取编译命令的方法
def create_command_infos(logger, build_path, output, verbose_list=[], build_args=""):
    is_exist = False

    make_file = build_path + os.path.sep + DEFAULT_SCONSTRUCT_NAME
    if not os.path.exists(make_file): raise IOError("No SConstruct in " + build_path)

    has_verbose = False
    outlines = []
    for verbose in verbose_list:
        cmd = "cd {}; scons -n {} {}=1".format(build_path, build_args, verbose)
        logger.info("try to execute command: " + cmd)
        print cmd
        p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if p.returncode == 0:
            out, err = p.communicate()
            if check_command_format(out):
                has_verbose = True
                outlines = out
                break
        logger.info("%s; excute fail." % cmd)

    if has_verbose:
        output.writelines(outlines)
    return output


def parse_flags(logger, build_log_in, build_dir,
                other_cc_compiles=None, other_cxx_compiles=None):
    """Compiler commands analysis may be similar process with make -n"""
    return parse_make.parse_flags(logger, build_log_in, build_dir,
                                  other_cc_compiles, other_cxx_compiles)


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
