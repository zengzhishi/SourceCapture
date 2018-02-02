# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_make.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-02-02 14:25:36
    @LastModif: 2018-02-02 14:26:29
    @Note:  TODO: 完成一般 Makefile 的解析
"""

import os
import re
import subprocess


def create_infos(root_path, output_path, makefile_name="Makefile", make_args=None):
    """
    创建info文件
    :param root_path:
    :param output_path:
    :param makefile_name:
    :param make_args:
    :return:
    """
    make_file = root_path + os.path.sep + makefile_name
    if not os.path.exists(make_file):
        raise IOError("No Makefile in " + root_path)

    cmd = "cd " + root_path + "; make -n -p -k "
    if make_args:
        cmd += make_args

    print cmd

    p = subprocess.Popen(cmd, shell=True, \
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = p.communicate()
    fileout = open(output_path + "/make_info.txt", "w")
    fileout.writelines(out)
    fileout.close()


def block_read(fin):
    # 去掉block前的空行
    line = fin.readline()
    while not line.strip("\n"):
        line = fin.readline()
    # 存储block的数据
    lines = []
    while line.strip("\n") != "":
        lines.append(line.strip("\n"))
        line = fin.readline()
    return lines


def analysis_block(lines):
    """
    解析块行的配置,得到目标文件所需要的参数
    :param lines:
    :return:
    """
    # 非目标, 可能是依赖文件或内置对象
    if lines[0] == "# Not a target:":
        return {}

    print lines[0]
    target, depend = re.split("\s*:\s*", lines[0])
    if len(depend) == 0:
        # 伪目标, 暂时先不管, 后面有需要再完成
        params_dict = {}
    else:
        targets = re.split("\s+", target)
        depends = re.split("\s+", depend)
        params_dict = {
            "target": targets,
            "depends": depends,
            "auto_params": {},
            "commands": [],
            "need_params": {}
        }
        for line in lines:
            auto_param_match = re.match("(.*)\s+\:=\s+(.*)", line)
            if auto_param_match:
                key = auto_param_match.group(1)[2:]
                params_dict["auto_params"][key] = auto_param_match.group(2)
                continue
            if line[0] == "\t":
                # for command line
                line_data = line.strip("\t")
                lst = re.split("\s+", line_data)
                params_dict["commands"].append(lst)
                for slice in lst:
                    args = re.findall(r"\$\((\w+)\)", slice)
                    if len(args):
                        for arg in args:
                            params_dict["need_params"][arg] = ""
    return params_dict


def print_info_analysis(output_path, targets=None):
    """
    解析文件的内容, 获取目标文件所需要的参数
    :param output_path:
    :param targets: 如果为None, 则默认把所有非伪目标的编译命令参数都获取回来
    :return:
    """
    fin = open(output_path + "/make_info.txt", "r")
    all_need_params = []
    all_params_dicts = []
    line = fin.readline()
    while line != '':
        # 1. 先找到目标行
        while line.strip("\n") != '# Files':
            line = fin.readline()
        # 2. 开始读取配置块
        lines = block_read(fin)
        while lines[-1] != "# VPATH Search Paths":
            # 3. 解析块
            config_param = analysis_block(lines)
            if len(config_param) == 0:
                # 非目标
                pass
            else:
                # 目标
                all_params_dicts.append(config_param)
                for arg in config_param["need_params"]:
                    all_need_params.append(arg)
            lines = block_read(fin)
        # 3. Files区读取完毕,继续跳过
    return all_params_dicts, all_need_params


def modify_makefile(echo_args, root_path, \
                    makefile, new_makefile, phony_target="capture_echo_values"):
    """
    复制原来的makefile, 并将参数输出的伪目标语句加入到新的Makefile中, 形成新的makefile
    :param echo_args:
    :param root_path:
    :param makefile:
    :param new_makefile:
    :param phony_target:
    :return:
    """
    pass


def exec_makefile(new_makefile, field_name):
    """
    执行修改之后的makefile的伪目标, 并将参数的结果解析之后返回
    :param new_makefile:
    :param field_name:
    :return:
    """
    pass


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
