#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import subprocess
import Queue

import utils.parse_cmake as parse_cmake
import utils.parse_make as parse_make


def get_system_path(compiler):
    """
    获取gcc系统头文件路径
    """
    # 查询 c 系统头文件路径
    cmd = "echo 'main(){}' | " + compiler + " -E -x c -v -"
    # 查询 c++ 系统头文件路径
    cpp_cmd = """echo 'main(){}' | gcc -E -x c++ -v -"""
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    retval = p.wait()
    lines = []
    for line in p.stdout.readlines():
        lines.append(line.strip())
    if retval == 0:
        return lines, True
    else:
        return lines, False


def get_directions(path):
    """获取指定路径下的所有目录"""
    paths = []
    for one in os.listdir(path):
        if os.path.isdir(path + "/" + one):
            paths.append(one)
    return paths


# cmake project
def check_cmake(path, project_path, cmake_build_path):
    """
    检查是否有CMakeList.txt
    :param path:
    :return:        bool
    """
    #check CMakeList.txt is exist
    if not cmake_build_path:
        cmake_build_path = project_path
    present_build_path = get_relative_build_path(path, project_path, cmake_build_path)
    if os.path.exists(path + "/CMakeLists.txt") \
            and os.path.exists(present_build_path + "/CMakeFiles"):
        return True
    return False


def check_cmake_exec_dest_dirname(file_name):
    """
    防止异常目录干扰
    :param file_name:
    :return:
    """
    if file_name[-4:] == ".dir":
        return True
    return False


def get_relative_build_path(path, project_path, cmake_build_path):
    abs_project_path = os.path.abspath(project_path)
    abs_present_path = os.path.abspath(path)
    relative_path = abs_present_path[len(abs_project_path):]
    present_build_path = cmake_build_path + relative_path
    return present_build_path


def set_default(infos):
    """TODO: 需要设置一下基本的宏定义和编译flags"""
    infos["flags"] = ["-fPIC", "-o2"]
    infos["definitions"] = ["HAVE_CONFIG_H"]
    return


def get_cmake_info(present_path, project_path, cmake_build_path=None):
    """
    搜索指定目录下CMakeFiles中的生成目录，并解析出目录下的源文件所需要的编译参数

    :param present_path:                            当前检索路径
    :param project_path:                            项目根路径
    :param cmake_build_path:                        cmake外部编译路径
    :return:
    """
    present_build_path = present_path
    if cmake_build_path:
        final_build_path = cmake_build_path
    else:
        final_build_path = project_path
    present_build_path = get_relative_build_path(present_path, project_path, final_build_path)
    cmake_files_path = present_build_path + "/CMakeFiles"
    info_list = []

    def _get_abs_path(path):
        if path[0] == "/":
            return path
        return os.path.abspath(final_build_path + "/" + path)

    for file_name in os.listdir(cmake_files_path):
        file_path = cmake_files_path + "/" + file_name
        if os.path.isdir(file_path) and check_cmake_exec_dest_dirname(file_name):
            # 目标目录
            flags_file = file_path + "/flags.make"
            depend_file = file_path + "/DependInfo.cmake"
            if os.path.exists(flags_file) and os.path.exists(depend_file):
                cmake_infos = parse_cmake.parse_cmakeInfo(depend_file)
                origin_flags, origin_custom_flags, origin_custom_definitions = parse_cmake.parse_flags(flags_file)
                for [depend_files, definitions, includes, compiler_type], flags in zip(cmake_infos, origin_flags):
                    includes = map(lambda relative_path: _get_abs_path(relative_path), includes)
                    custom_flags = {}
                    custom_definitions = {}
                    depend_s_files = filter(lambda file: file[-2:] != ".o", depend_files)
                    for key in origin_custom_flags:
                        abs_file_path = final_build_path + os.path.sep + key
                        if abs_file_path in depend_files:
                            index = depend_files.index(abs_file_path)
                            source_file_path = depend_files[index - 1]
                            index = depend_s_files.index(source_file_path)
                            custom_flags[index] = origin_custom_flags[key]
                    for key in origin_custom_definitions:
                        abs_file_path = final_build_path + os.path.sep + key
                        if abs_file_path in depend_files:
                            index = depend_files.index(abs_file_path)
                            source_file_path = depend_files[index - 1]
                            index = depend_s_files.index(source_file_path)
                            custom_definitions[index] = origin_custom_definitions[key]
                    info_list.append({
                        "source_files": depend_s_files,
                        "flags": flags,
                        "definitions": definitions,
                        "includes": includes,
                        "compiler_type": compiler_type,
                        "custom_flags": custom_flags,
                        "custom_definitions": custom_definitions
                    })

    # 对于有定义CMakeLists.txt文件，但是没有配置编译选项的情况
    if len(info_list) == 0:
        info_list.append({
            "source_files": [],
            "flags": [],
            "definitions": [],
            "includes": [],
            "compiler_type": ""
        })
    return info_list


def cmake_project_walk(root_path, prefers, cmake_build_path=None):
    """
    寻找根路径下project组成, 返回应该以CMake的一个set为准
    :param root_path:
    :param prefers:
    :return:    [present_path, files_s_infos, files_h]
        files_s_infos -> list
        files_s_infos = [[files_s, flags, defs, includes, exec_path], ...]
        其中files_s 是可以与其他元素内的重复的，最终决定编译目标文件hash的是文件名路径+编译参数
        files_s 甚至可以能使用到其他目录的文件
        对于没能在cmake中找到的源文件，则可以将includes继承所有，flags设置一些通用的就行，defs使用HAVE_CONFIG这种可以判断的
        最后一组则是对剩下的未配置源文件和头文件进行整理返回
    """
    source_file_suffix = set(["cpp", "c", "cc", "cxx"])
    include_file_suffix = set(["h", "hpp"])
    to_walks = Queue.Queue()
    to_walks.put(root_path)
    # 已经添加过的源文件，将记录下来，除了cmake指定要重复编译，否则不做特殊处理
    used_file_s_set = set()
    # 添加所有include，提供给未指定的源文件编译
    include_set = set()
    # 添加关注目录
    prefer_paths = set()
    for name in prefers:
        file_path = root_path + "/" + name
        prefer_paths.add(file_path)

    level = 0
    other_file_s = []
    while not to_walks.empty():
        present_path = to_walks.get()
        if check_cmake(present_path, root_path, cmake_build_path):
            print "\tscan path:" + present_path
            info_list = get_cmake_info(present_path, root_path, cmake_build_path)
            if cmake_build_path:
                exec_path = cmake_build_path
            else:
                exec_path = root_path
            # 更新
            for data_dict in info_list:
                for file in data_dict["source_files"]:
                    used_file_s_set.add(file)
                for include in data_dict["includes"]:
                    include_set.add(include)
                data_dict["exec_directory"] = exec_path
                data_dict["config_from"] = present_path
            yield info_list

        for file_name in os.listdir(present_path):
            file_path = present_path + "/" + file_name
            file_path = os.path.abspath(file_path)
            if os.path.isdir(file_path):
                if not level:
                    if file_path in prefer_paths:
                        to_walks.put(file_path)
                else:
                    if file_name[0] != '.':
                        to_walks.put(file_path)
            else:
                if file_path not in used_file_s_set:
                    slice = file_name.split('.')
                    suffix = slice[-1]
                    if suffix in source_file_suffix or suffix in include_file_suffix:
                        other_file_s.append(file_path)
        level = 1

    # 最后构造一份未被cmake定义的源文件的list
    undefind_files = []
    for file_path in other_file_s:
        if file_path not in used_file_s_set:
            undefind_files.append(file_path)
    # 同项目路径下的源文件，已经显示被cmake定义的文件的依赖，很大可能是相同的，因此将全部取过来给这部分的源文件使用
    includes = list(include_set)
    undefind_info_list = [{
        "source_files": undefind_files,
        "flags": [],
        "definitions": [],
        "includes": includes,
        "exec_directory": root_path,
        "compiler_type": ""
    }]
    yield undefind_info_list


def get_present_path_cmake(root_path, prefers, cmake_build_path=None):
    """
    针对与CMake构建的项目，需要特殊处理一点，不能直接遍历.

    :param root_path:               项目根路径
    :param prefers:                 关注目录
    :param cmake_build_path:        指定cmake build路径
    :return:
        source_infos
        include_files
        files_count
    """
    # TODO: 这些set可以写到globle中，没必要每个地方配置一个
    source_file_suffix = set(["cpp", "c", "cc", "cxx", "c++"])
    c_file_suffix = set(["c"])
    cxx_file_suffix = set(["cpp", "cxx", "cc", "c++"])
    include_file_suffix = set(["h", "hpp"])
    if len(prefers) == 0:
        prefers = ["src", "include", "lib", "modules"]

    source_infos = []
    files_count = 0
    include_files = []
    cxx_files_info = {
        "source_files": [],
        "exec_directory": root_path,
        "compiler_type": "CXX"
    }
    # TODO：对于未定义的源文件，需要返回记录，但是不需要构建编译命令
    for info_list in cmake_project_walk(root_path, prefers, cmake_build_path):
        for info in info_list:
            if len(info["source_files"]) == 0:
                continue
            if not info["compiler_type"]:
                set_default(info)
                cxx_files_info["flags"] = info["flags"]
                cxx_files_info["definitions"] = info["definitions"]
                cxx_files_info["includes"] = info["includes"]
                lefts_s = []
                for file in info["source_files"]:
                    slice = file.split('.')
                    suffix = slice[-1]
                    if suffix not in source_file_suffix:
                        include_files.append(file)
                    else:
                        if suffix in cxx_file_suffix:
                            cxx_files_info["source_files"].append(file)
                        elif suffix in c_file_suffix:
                            lefts_s.append(file)
                        files_count += 1
                info["source_files"] = lefts_s
                info["compiler_type"] = "C"
            else:
                files_count += len(info["source_files"])
            source_infos.append(info)
    if len(cxx_files_info["source_files"]):
        source_infos.append(cxx_files_info)

    return source_infos, include_files, files_count


# autotools project
def get_definitions(path):
    ## TODO 可以选择一个类来封装，使得该方法可以被重写
    """获取当前路径下Makefile.am中的宏定义"""
    cmd = "grep \"^AM_CPPFLAGS*\" " + path + "/Makefile.am | awk '{print $3}'"
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    retval = p.wait()
    definitions = []
    for line in p.stdout.readlines():
        if line[1] == 'D':
            definitions.append(line.strip())
    return definitions


def autotools_project_walk(root_path, prefers):
    """目录遍历迭代器，遍历项目并获取对应的宏定义"""
    to_walks = Queue.Queue()

    definitions = get_definitions(root_path)
    to_walks.put((root_path, definitions))
    present_path = ""

    prefer_paths = set()
    for name in prefers:
        file_path = root_path + "/" + name
        prefer_paths.add(file_path)

    level = 0
    while not to_walks.empty():
        (present_path, old_definitions) = to_walks.get()
        definitions = get_definitions(present_path)
        def_str = ""

        if len(definitions) == 0:
            definitions = old_definitions

        for def_s in definitions:
            def_str += " " + def_s

        filelists = os.listdir(present_path)
        files = []
        for file_name in filelists:
            file_path = present_path + "/" + file_name
            if os.path.isdir(file_path):
                if not level:
                    if file_path in prefer_paths:
                        to_walks.put((file_path, definitions))
                else:
                    if file_name[0] != '.':                         # 排除了隐藏文件
                        to_walks.put((file_path, definitions))
            else:
                files.append(file_name)
        level = 1
        yield (present_path, files, def_str)


def get_present_path_autotools(root_path, prefers):
    """
    遍历项目的目录结构，获取project_info
    Args:
        root_path:          项目根目录
        prefers:            关注路径（全选时，可能会出现example等涉及到未安装对应库的文件失败，
                            因为configure的环境一般不管范例里面涉及的额外模块）。

    Returns:
        sub_paths:          子目录（用于添加include路径）
        source_files:       源文件
        include_files:      头文件
        source_defs:        源文件编译所需要的宏定义（与源文件一一对应）
    """
    if len(prefers) == 0:
        prefers = ["src", "include", "lib", "modules"]
    source_file_suffix = set(["cpp", "c", "cc", "cxx", "c++"])
    include_file_suffix = set(["h", "hpp"])

    root_path_length = len(root_path)
    paths = []
    files_s_defs = []
    files_s = []
    files_h = []
    for line_tulpe in autotools_project_walk(root_path, prefers):
        folder = line_tulpe[0]
        file_names = line_tulpe[1]
        definition = line_tulpe[2]
        paths.append(folder)
        for file_name in file_names:
            slice = file_name.split('.')
            suffix = slice[-1]
            if len(slice) > 1:
                if suffix in source_file_suffix:
                    output_name_prefix = folder[root_path_length + 1:].replace("/", "_")
                    files_s.append((folder + "/" + file_name, output_name_prefix))
                    files_s_defs.append(definition)
                elif suffix in include_file_suffix:
                    files_h.append(folder + "/" + file_name)
    return paths, files_s, files_h, files_s_defs


# GNU make project
def selective_walk(root_path, prefers):
    to_walks = Queue.Queue()

    to_walks.put(root_path)

    prefer_paths = set()
    for name in prefers:
        file_path = root_path + "/" + name
        prefer_paths.add(file_path)

    level = 0
    while not to_walks.empty():
        present_path = to_walks.get()

        files = []
        for file_name in os.listdir(present_path):
            file_path = present_path + "/" + file_name
            if os.path.isdir(file_path):
                if not level:
                    if file_path in prefer_paths:
                        to_walks.put(file_path)
                else:
                    if file_name[0] != '.':                         # 排除了隐藏文件
                        to_walks.put(file_path)
            else:
                files.append(file_name)
        level = 1
        yield (present_path, files)


def get_present_path_make(logger, root_path, prefers, build_path=None, output_path=None, build_args=None):
    """
    :param root_path:               根路径
    :param prefers:                 关注目录
    :return:
    """
    if len(prefers) == 0:
        prefers = ["src", "include", "lib", "modules"]

    source_file_suffix = set(["cpp", "c", "cc", "cxx", "c++"])
    include_file_suffix = set(["h", "hpp"])
    paths = []
    files_s = []
    files_h = []
    for line_tulpe in selective_walk(root_path, prefers):
        folder = line_tulpe[0]
        file_paths = line_tulpe[1]
        paths.append(folder)
        for file_path in file_paths:
            slice = file_path.split('.')
            suffix = slice[-1]
            if len(slice) > 1:
                if suffix in source_file_suffix:
                    files_s.append(folder + "/" + file_path)
                elif suffix in include_file_suffix:
                    files_h.append(folder + "/" + file_path)

    if not build_path:
        build_path = root_path
    if not output_path:
        try:
            import tempfile
            output = tempfile.TemporaryFile()
        except ImportError:
            output_path_file = "/tmp/make_infos.txt"
            output = open(output_path_file, "w + b")
    else:
        output = open(output_path + "/make_infos.txt", "w + b")

    if build_args:
        output = parse_make.create_command_infos(logger, build_path, output, make_args=build_args)
    else:
        output = parse_make.create_command_infos(logger, build_path, output)
    output.seek(0)
    line_count, skip_count, compile_db = parse_make.parse_flags(logger, output, build_path)
    output.close()
    logger.info("Parse make building result: [line_count: %d] [skip_count: %d]" % \
                (line_count, skip_count))
    return paths, files_s, files_h, compile_db


def get_present_path(root_path, prefers):
    if len(prefers) == 0:
        prefers = ["src", "include", "lib", "modules"]

    source_file_suffix = set(["cpp", "c", "cc", "cxx", "c++"])
    include_file_suffix = set(["h", "hpp"])
    paths = []
    files_s = []
    files_h = []
    for line_tulpe in selective_walk(root_path, prefers):
        folder = line_tulpe[0]
        file_paths = line_tulpe[1]
        paths.append(folder)
        for file_path in file_paths:
            slice = file_path.split('.')
            suffix = slice[-1]
            if len(slice) > 1:
                if suffix in source_file_suffix:
                    files_s.append(folder + "/" + file_path)
                elif suffix in include_file_suffix:
                    files_h.append(folder + "/" + file_path)
    print files_s

    return paths, files_s, files_h
