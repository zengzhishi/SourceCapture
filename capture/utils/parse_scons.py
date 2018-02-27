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

DEFAULT_SCONSTRUCT_NAME = "SConstruct"

# 使用 make -Bnkw 方式获取编译命令的方法
def create_command_infos(logger, build_path, output, verbose_list=[], build_args=""):
    is_exist = False

    make_file = build_path + os.path.sep + DEFAULT_SCONSTRUCT_NAME
    if not os.path.exists(make_file):
        raise IOError("No SConstruct in " + build_path)

    for verbose in verbose_list:
    cmd = "cd {}; scons -n {}".format(build_path, build_args)

    logger.info("execute command: " + cmd)
    print cmd
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = p.communicate()
    output.writelines(out)
    return output


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
