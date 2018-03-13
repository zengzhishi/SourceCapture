# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_cmake.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-29 17:45:26
    @LastModif: 2018-01-29 19:25:11
    @Note: CMake Output data analysis.
"""

import re
import os


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
    Analyze set function in DependInfo.cmake.
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

        # get line with comment, and remove comment part
        setting_line_with_comment = re.match(r".+#\S*", line)
        if setting_line_with_comment:
            line = re.split("\s+\#", line)[0]

        if line == ")":
            continue

        # match one line config
        oneline_result = re.match("set\((\S+)\s+(\S+)\)", line)
        if oneline_result:
            config[oneline_result.group(1)] = strip_quotation(oneline_result.group(2))
            continue

        # match multi-line config
        start_result = re.match("set\((\S+)\s*", line)
        if start_result:
            temp_key = start_result.group(1)
            config[temp_key] = []
            continue

        # match configure line
        args_result = re.split(r'"\s+"', line)
        if args_result[-1][-1] == ')':
            args_result[-1] = args_result[-1][:-1]
            temp_key = ""

        for arg in args_result:
            if temp_key in config:
                arg = strip_quotation(arg)
                check_equal = re.match("(.*)=(.*)", arg)
                if check_equal:
                    key = check_equal.group(1)
                    value = check_equal.group(2)
                    if re.match("[\"\'](.*)[\"\']", value):
                        value = value.replace("\"", "\\\"")
                    else:
                        value = "\"" + value + "\""
                    arg = key + "=" + value
                config[temp_key].append(arg)
            else:
                config[temp_key] = []
    return config


def parse_flags(flags_file):
    """
    Analyze cmake flags.make
    :param flags_file:
    :return: final_flags, custom_flags, custom_definitions
    """
    flags_set = ["CXX_FLAGS", "C_FLAGS"]
    fin = open(flags_file, "r")
    data = [None, None]
    custom_definitions = {}
    custom_flags = {}
    for line in fin:
        line = line.strip(' \t\n')
        # Skip comment and empty line
        if len(line) == 0:
            continue
        if line[0] == '#':
            # line start with '#' can be a comment line or custom configure line
            custom_flag = re.match(r"# Custom flags: (.*)_FLAGS = (.*)", line)
            if custom_flag:
                relative_file_path = custom_flag.group(1)
                custom_flag_data = custom_flag.group(2)
                file_custom_flags = re.split("\s+(?=-)", custom_flag_data)
                custom_flags[relative_file_path] = file_custom_flags
                continue

            custom_definition = re.match("# Custom defines: (.*)_DEFINES = (.*)", line)
            if custom_definition:
                relative_file_path = custom_definition.group(1)
                custom_definition_data = custom_definition.group(2)
                file_custom_definitions = re.split(";", custom_definition_data)
                custom_definitions[relative_file_path] = file_custom_definitions
                continue
        # Get line with comment, and remove comment part
        setting_line_with_comment = re.match(r".+#\S*", line)
        if setting_line_with_comment:
            line = re.split("\s+\#", line)[0]

        lst = re.split(r"\s+=\s*", line)
        if lst[0] == flags_set[0]:
            data[0] = lst[1]
        elif lst[0] == flags_set[1]:
            data[1] = lst[1]
    final_flags = []
    if data[0] is not None and data[1] is not None:
        for flag in data:
            flags = re.split("\s+(?=-)", flag)
            final_flags.append(flags)
    elif data[1] is None:
        flags = re.split("\s+(?=-)", data[0])
        final_flags = [flags,]
    elif data[0] is None:
        flags = re.split("\s+(?=-)", data[1])
        final_flags = [flags,]
    return final_flags, custom_flags, custom_definitions


def parse_cmakeInfo(depen_file):
    """
    Analyze DependInfo.cmake
    :param file:    DependInfo.cmake file path
    :return: files_s, definitions, includes
    """
    fin = open(depen_file, 'r')
    config_dict = set_analysis(fin)

    if isinstance(config_dict["CMAKE_DEPENDS_LANGUAGES"], list):
        compiler_type = config_dict["CMAKE_DEPENDS_LANGUAGES"]
    else:
        compiler_type = (config_dict["CMAKE_DEPENDS_LANGUAGES"],)

    cmake_infos = []

    if "CXX" in compiler_type:
        source_field_cxx = "CMAKE_DEPENDS_CHECK_CXX"
        definition_field_cxx = "CMAKE_TARGET_DEFINITIONS_CXX"
        include_field_cxx = "CMAKE_CXX_TARGET_INCLUDE_PATH"
        files_cxx, definitions_cxx, includes_cxx = [], [], []
        if source_field_cxx in config_dict:
            files_cxx = config_dict[source_field_cxx]
            # files_cxx = filter(lambda file: file[-2:] != ".o", files_cxx)
        if definition_field_cxx in config_dict:
            definitions_cxx = config_dict[definition_field_cxx]
        if include_field_cxx in config_dict:
            includes_cxx = config_dict[include_field_cxx]
        cmake_infos.append([files_cxx, definitions_cxx, includes_cxx, "CXX"])

    if "C" in compiler_type:
        source_field_c = "CMAKE_DEPENDS_CHECK_C"
        definition_field_c = "CMAKE_TARGET_DEFINITIONS_C"
        include_field_c = "CMAKE_C_TARGET_INCLUDE_PATH"
        files_c, definitions_c, includes_c = [], [], []
        if source_field_c in config_dict:
            files_c = config_dict[source_field_c]
            # files_c = filter(lambda file: file[-2:] != ".o", files_c)
        if definition_field_c in config_dict:
            definitions_c = config_dict[definition_field_c]
        if include_field_c in config_dict:
            includes_c = config_dict[include_field_c]
        cmake_infos.append([files_c, definitions_c, includes_c, "C"])

    return cmake_infos

