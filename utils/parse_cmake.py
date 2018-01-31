# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_cmake.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-29 17:45:26
    @LastModif: 2018-01-29 19:25:11
    @Note: 用于解析cmake的文件
"""

import re
import os

import types


def strip_quotation(string):
    if (string[0] == "\"" and string[-1] == "\"") \
            or (string[0] == "\'" and string[-1] == "\'"):
        return string[1:-1]
    elif string[0] == "\"" or string[0] == "\'":
        return string[1:]
    elif string[-1] == "\"" or string[-1] == "\'":
        return string[:-1]
    else:
        return string


def set_analysis(fin):
    """
    解析DependInfo.cmake文件的set语句设置项
    :param fin:
    :return:
    """
    config = {}
    temp_key = ""
    for line in fin:
        line = line.strip(' \t\n')
        # 跳过注释和空行
        if len(line) == 0 or line[0] == '#':
            continue

        # 获取带comment的行， 并去除行尾的注释
        setting_line_with_comment = re.match(r".+#\S*", line)
        if setting_line_with_comment:
            line = re.split("\s+\#", line)[0]

        # TODO: 暂时这里直接跳过，默认当做cmake产生的文件不会出错，存在隐患
        if line == ")":
            continue

        # 匹配oneline config
        oneline_result = re.match("set\((\S+)\s+(\S+)\)", line)
        if oneline_result:
            config[oneline_result.group(1)] = strip_quotation(oneline_result.group(2))
            continue

        # 获得到multiline config 的头
        start_result = re.match("set\((\S+)\s*", line)
        if start_result:
            temp_key = start_result.group(1)
            config[temp_key] = []
            continue

        # 获取配置行
        args_result = re.split(r'"\s+"', line)
        if args_result[-1][-1] == ')':
            args_result[-1] = args_result[-1][:-1]
            temp_key = ""

        for arg in args_result:
            if temp_key in config:
                config[temp_key].append(strip_quotation(arg))
            else:
                config[temp_key] = []
    return config


def parse_flags(flags_file):
    flags_set = set(["CXX_FLAGS", "C_FLAGS"])
    fin = open(flags_file, "r")
    data = ""
    for line in fin:
        line = line.strip(' \t\n')
        # 跳过注释和空行
        if len(line) == 0 or line[0] == '#':
            continue
        # 获取带comment的行， 并去除行尾的注释
        setting_line_with_comment = re.match(r".+#\S*", line)
        if setting_line_with_comment:
            line = re.split("\s+\#", line)[0]

        lst = re.split(r"\s+=\s+", line)
        if lst[0] in flags_set:
            data = lst[1]
            break
    flags = re.split("\s+(?=-)", data)
    return flags


def parse_cmakeInfo(depen_file):
    """
    解析DependInfo.cmake文件
    TODO: 这里返回的include路径是相对路径，因此，我的代码需要改成跳转到指定目录下执行
    :param file:    DependInfo.cmake的文件路径
    :return: files_s, definitions, includes
    """
    fin = open(depen_file, 'r')
    config_dict = set_analysis(fin)

    compiler_type = ""
    if type(config_dict["CMAKE_DEPENDS_LANGUAGES"]) == types.ListType:
        compiler_type = config_dict["CMAKE_DEPENDS_LANGUAGES"][0]
    else:
        compiler_type = config_dict["CMAKE_DEPENDS_LANGUAGES"]

    # 获取不同编译器的域名
    source_field = "CMAKE_DEPENDS_CHECK_C"
    definition_field = "CMAKE_TARGET_DEFINITIONS_C"
    include_field = "CMAKE_C_TARGET_INCLUDE_PATH"
    if compiler_type == "CXX":
        source_field = "CMAKE_DEPENDS_CHECK_CXX"
        definition_field = "CMAKE_TARGET_DEFINITIONS_CXX"
        include_field = "CMAKE_CXX_TARGET_INCLUDE_PATH"
    elif compiler_type == "C":
        pass
    else:
        raise Exception("compler type unsuport")

    files = config_dict[source_field]
    definitions = config_dict[definition_field]
    includes = config_dict[include_field]

    files_s = filter(lambda file: file[-2:] != ".o", files)

    return files_s, definitions, includes

