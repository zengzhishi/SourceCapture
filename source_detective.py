#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import re
import os
import sys
import subprocess
import Queue
import logging
import logging.config
import parse_logger

#logging.config.fileConfig("logging.conf")
#logger = logging.getLogger("compileLog")


def get_system_path():
    """
    获取gcc系统头文件路径
    """
    cmd = """echo 'main(){}' | gcc -E -x c -v -"""                              # 查询 c 系统头文件路径
    cpp_cmd = """echo 'main(){}' | gcc -E -x c++ -v -"""                        # 查询 c++ 系统头文件路径
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    retval = p.wait()
    lines = []
    for line in p.stdout.readlines():
        lines.append(line.strip())
    if retval == 0:
        return lines, True
    else:
        return lines, False


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


def selective_walk(root_path, prefers):
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


def get_present_path2(root_path, prefers):
    """
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
    source_file_suffix = set("cpp, c, cc")
    include_file_suffix = set("h, hpp")

    root_path_length = len(root_path)
    paths = []
    files_s_defs = []
    files_s = []
    files_h = []
    for line_tulpe in selective_walk(root_path, prefers):
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


def get_present_path(root_path):
    """
    获取源码路径下的子路径
    """
    source_file_suffix = set("cpp, c, cc")
    include_file_suffix = set("h, hpp")
    paths = []
    files_s = []
    files_h = []
    for line_tulpe in os.walk(root_path):
        print line_tulpe
        folder = line_tulpe[0]
        file_paths = line_tulpe[-1]
        paths.append(folder)
        for file_path in file_paths:
            slice = file_path.split('.')
            suffix = slice[-1]
            if len(slice) > 1:
                print "="*20 + suffix
                if suffix in source_file_suffix:
                    files_s.append(folder + "/" + file_path)
                elif suffix in include_file_suffix:
                    files_h.append(folder + "/" + file_path)
    return paths, files_s, files_h


def get_dir(path):
    paths = []
    for one in os.listdir(path):
        if os.path.isdir(path + "/" + one):
            paths.append(one)
    return paths


if __name__ == "__main__":
    output_path = ""
    if len(sys.argv) == 2:
        input_path = sys.argv[1]
        prefers_str = ""
    elif len(sys.argv) == 3:
        input_path = sys.argv[1]
        prefers_str = sys.argv[2]
    elif len(sys.argv) == 4:
        # 增加了输出目录
        input_path = sys.argv[1]
        prefers_str = sys.argv[2]
        output_path = sys.argv[3]
    else:
        sys.stderr.write("""Please input project root path to compiler.
    Usage:
        ./program_name root_path [prefer_sub_folder1,prefer_sub_folder2,...] [outer_output_path]
""")
        sys.exit()

    if len(input_path) > 1 and input_path[-1] == '/':
        input_path = input_path[:-1]


    # 设置编译脚本输出目录和日志输出
    logger_builder = parse_logger.logger_analysis("capture.cfg")
    command_output_path = input_path
    if output_path:
        command_output_path = output_path
        logger = logger_builder.get_Logger("simpleExample", output_path + "/capture.log")
    else:
        logger = logger_builder.get_Logger("simpleExample", "capture.log")

    logger.info("Loading config complete")

    if prefers_str == "":
        prefers = []
    elif prefers_str == "all":
        prefers = get_dir(input_path)
    else:
        prefers = prefers_str.split(",")
    logger.debug("prefer directories: " + str(prefers))

    logger.info("Start Scaning project folders...")
    # system_paths, status = get_system_path()
    sub_paths, files_s, files_h, files_s_defs = get_present_path2(input_path, prefers)
    logger.info("End of Scaning project folders...")

    # add Include path
    gcc_include_string = ""
    for path in sub_paths:
        gcc_include_string = gcc_include_string + " " + "-I" + path

    # TODO 对输出命令进行构建，可以抽取成一个单独的模块
    gcc_string = "gcc"

    logger.info("checking configure file...")
    is_has_configure = os.path.exists(input_path + "/configure")
    if is_has_configure:
        logger.info(input_path + "/configure" + " is exists.")
        gcc_string += " -DHAVE_CONFIG_H"

    # 导出目录扫描数据
    import capture
    logger.info("Dumping scaned data")
    source_files = [x[0] for x in files_s]
    capture.scan_data_dump(command_output_path + "/" + "project_scan.json",
            source_files,
            files_s_defs,
            files_h,
            sub_paths,
            is_has_configure
            )
    logger.info("Dumping scaned data success")

    commands = []
    logger.info("Start building compile commands")
    with open(command_output_path + "/" + "my_compile.sh", "w+") as fout:
        for source_file_tuple, definition in zip(files_s, files_s_defs):
            source_file = source_file_tuple[0]
            suffix = source_file.split(".")[-1]
            index = -(len(suffix))
            file_name = source_file.split("/")[-1]
            file_index = -(len(file_name) + 1)
            output_path_str = output_path
            if not output_path_str:
                output_path_str = source_file[:file_index]
            else:
                # 设置输出目录
                output_path_str = output_path_str + "/fileCache"
                if not os.path.exists(output_path_str):
                    os.makedirs(output_path_str)
            output_file_path = output_path_str + "/" + source_file_tuple[1] + "_" + file_name[:index] + "o"
            makestring = gcc_string + definition + " -c " + source_file + " -o " + output_file_path + gcc_include_string
            fout.write(makestring + "\n")
            commands.append(makestring)

    logger.info("Dumping compiler commands complete")

    logger.info("Start dumping commands")
    # 导出生成的编译命令
    capture.commands_dump(command_output_path + "/compile_commands.json",
            source_files,
            commands,
            [command_output_path for i in source_files]
            )
    logger.info("Dumping commands success")

    logger.info("Complete")

