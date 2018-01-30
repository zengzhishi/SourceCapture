#!/usr/bin/env python2
# -*- coding: utf-8 -*-

#################################################################################################
#  TODO:
#  1. 改变目录搜索获取参数的方式，针对与可以使用cmake的目录，可以采用更加方便的方式，
#  通过获取每个含有CMakeList.txt目录下的flags.make，可以获得编译参数，头文件引用路径，和宏定义
#  需要做的工作只是获取这些，同时返回有哪些头文件和源文件即可，遍历上不需要将所有自路径都添加进来
#  2. 针对使用automake工具的项目，还需要研究一下
#  3. 针对直接使用Makefile的，可以通过添加一个伪目标，利用@echo来输出需要使用到的FLAGS参数，
#  但是由于命名和写法的不一致，可能需要做整个依赖关系的解析，得到最终需要使用到的flag参数对应的
#  变量
#
#################################################################################################

import re
import os
import sys
import subprocess
import Queue
import logging
import logging.config
import conf.parse_logger as parse_logger
import time

try:
    import redis
except ImportError:
    sys.path.append("./utils")
    import redis

import capture
import utils.parse_cmake as parse_cmake

SYSTEM_PATH_SEPERATE = "/"
COMPILE_COMMAND = "gcc"

# 并发构建编译命令
import building_process

class CommandBuilder(building_process.ProcessBuilder):
    def mission(self, queue, logger_pipe, result_dict, redis_instance, locks=[]):
        lock = locks[0]
        pid = os.getpid()
        logger_pipe.send(["info", "Process pid:%d start." % pid])
        lock.acquire()
        while not queue.empty():
            job_tuple = queue.get()
            lock.release()
            command_string = self.compile_command
            try:
                file_path = job_tuple[0]
                definition = job_tuple[1]
                flags = job_tuple[2]
            except IndexError:
                logger_pipe.send(["debug", "Process pid:%d job fail: [%s]" % str(job_tuple)])
                continue

            filename = file_path.split(SYSTEM_PATH_SEPERATE)[-1]
            # 文件名hash处理
            transfer_name = capture.source_path_MD5Calc(file_path)
            file_out_folder = ""
            file_index = -(len(filename) + 1)
            old_folder = file_path[:file_index]

            try:
                if self.output_path:
                    file_out_folder = self.output_path + "/fileCache"
                    if not os.path.exists(file_out_folder):
                            os.makedirs(file_out_folder)

                else:
                    file_out_folder = old_folder
            except OSError:
                # 目录创建失败直接退出进程
                logger_pipe.send(["critical", "creating directory fail: [%s]" % \
                        file_out_folder])
                return
            file_out_path = file_out_folder + SYSTEM_PATH_SEPERATE + transfer_name + ".o"

            try:
                capture.file_info_save(redis_instance, filename, old_folder, \
                    transfer_name, definition, flags)
            except redis.RedisError:
                # 信息保存失败，继续执行
                logger_pipe.send(["warning", \
                        "Source info for [%s] saving to redis fail." % transfer_name])


            command_string += definition
            command_string += " -c " + file_path
            command_string += " -o " + file_out_path
            command_string += self.include_path

            for flag in flags:
                command_string += " " + flag

            # 输出结果
            result_dict[transfer_name] = (file_path, command_string, self.output_path)
            lock.acquire()
        lock.release()

        logger_pipe.send(["info", "Process pid:%d Complete." % pid])
        return

    def distribute_jobs(self, compile_command, output_path, \
            files_s, defs, flags, sub_paths):
        self.compile_command = compile_command
        self.output_path = output_path
        self.include_path = ""

        for path in sub_paths:
            self.include_path += " " + "-I" + path

        for job_tuple in zip(files_s, defs, flags):
            self._queue.put(job_tuple)

    def run(self, process_log_path=None, worker_num=building_process.CPU_CORE_COUNT):
        """返回结果为dict

        Returns:
            result_dict:    {hash处理后的文件名: (源文件, 编译命令, 命令执行路径),...}

        """

        result_dict = self._manager.dict()
        self._logger.info("Multiprocess mission Start...")
        start_time = time.clock()

        # 设置进程日志
        if not process_log_path:
            filepath = self._logger.handlers[0].baseFilename
            filename = filepath.split("/")[-1]
            process_log_path = filepath[:-(len(filename) + 1)]
        process_logger = self._logger_config(process_log_path)


        # 设置日志信息管道
        self.__logger_pipe_r, self.__logger_pipe_w = building_process.multiprocessing.Pipe(duplex=False)

        # 添加任务完成度记录进程
        process_list = []
        p = building_process.multiprocessing.Process(target=self.log_total_missions, args=(self._queue,))
        process_list.append(p)
        p.start()

        pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
        for i in range(worker_num):
            redis_instance = redis.Redis(connection_pool=pool)
            p = building_process.multiprocessing.Process(target=self.mission, args=(self._queue, \
                    self.__logger_pipe_w, result_dict, redis_instance, self.lock))
            process_list.append(p)
            p.start()

        p_logger = building_process.multiprocessing.Process(target=self.mission_logger, \
                args=(self.__logger_pipe_r, process_logger,))
        p_logger.start()


        for p in process_list:
            p.join()

        # 在其他进程结束之后对日志模块发出结束信号
        self.__logger_pipe_w.send(["END"])
        p_logger.join()

        end_time = time.clock()

        self._logger.info("All Process Time: %f" % (end_time - start_time))
        self._logger.info("Multiprocess mission complete...")

        return result_dict

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


def check_cmake(path):
    """
    检查是否有CMakeList.txt
    :param path:
    :return:        bool
    """
    #check CMakeList.txt is exist
    if os.path.exists(path + "/CMakeList.txt"):
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


def get_cmake_info(path, cmake_build_path):
    """
    搜索指定目录下CMakeFiles中的生成目录，并解析出目录下的源文件所需要的编译参数
    :param path:                        源文件的目录（原定有用后来发现暂时还没有使用的必要）
    :param cmake_build_path:
    :return:
    """
    build_path = cmake_build_path + "/CMakeFiles"
    info_list = []

    for file_name in os.listdir(build_path):
        file_path = build_path + "/" + file_name
        if os.path.isdir(file_path) and check_cmake_exec_dest_dirname(file_name):
            # 目标目录
            flags_file = file_path + "/flags.make"
            depend_file = file_path + "/DependInfo.make"
            if os.path.exists(flags_file) and os.path.exists(depend_file):
                depend_s_files, definitions, includes = parse_cmake.parse_dependInfo(flags_file)
                flags = parse_cmake.parse_flags(depend_file)
                file_s_set = set(depend_s_files)
                info_list.append((file_s_set, flags, definitions, includes))

    if len(info_list) == 0:
        info_list.append(set(), [], [], [])
    return info_list


def cmake_project_walk(root_path, prefers, cmake_build_path):
    """
    寻找根路径下project组成, 返回应该以CMake的一个set为准
    :param root_path:
    :param prefers:
    :return:
    """
    to_walks = Queue.Queue()

    #[[file_s_set, flags, definitions, includes_ paths],]
    cmake_infos_list = get_cmake_info(root_path)

    #[[files, flags, definitions, includes, paths], ]
    transfer_infos = []

    to_walks.put((root_path, , root_path))
    present_path = ""

    prefer_paths = set()
    for name in prefers:
        file_path = root_path + "/" + name
        prefer_paths.add(file_path)

    level = 0
    while not to_walks.empty():
        (present_path, [flags, definitions, include_paths], exec_path) \
            = to_walks.get()

        if check_cmake(present_path):
            file_s_set, flags, definitions, include_paths = get_cmake_info(present_path)
            exec_path = present_path

        files = []
        for file_name in os.listdir(present_path):
            file_path = present_path + "/" + file_name
            if os.path.isdir(file_path):
                if not level:
                    if file_path in prefer_paths:
                        to_walks.put((file_path, flags, definitions, include_paths, exec_path))
                else:
                    if file_name[0] != '.':                         # 排除了隐藏文件
                        to_walks.put((file_path, flags, definitions, include_paths, exec_path))
            else:
                files.append(file_name)
        level = 1
        yield [(present_path, files, flags, definitions, include_paths, exec_path), ]


def get_present_path_cmake(root_path, prefers, is_outer_project=False, cmake_build_path=None):
    """
    针对与CMake构建的项目，需要特殊处理一点，不能直接遍历.

    :param root_path:               项目根路径
    :param prefers:                 关注目录
    :param is_outer_project:        是否为外部构建
    :param cmake_build_path:        指定cmake build路径
    :return:
        sub_paths:                  子目录（用于添加include路径）
        source_files:               源文件
        include_files:              头文件
        source_defs:                源文件编译所需要的宏定义（与源文件一一对应）
    """
    if len(prefers) == 0:
        prefers = ["src", "include", "lib", "modules"]
    source_file_suffix = set("cpp, c, cc")
    include_file_suffix = set("h, hpp")

    # iter 内使用，每次遍历返回回来的exec_path可能是相同的，所以需要extend文件
    exec_path = ""
    files_s = []
    files_h = []
    defs = []                   # defs应该与执行目录对应

    # 外部保存使用
    relative_paths = {exec_path: (files_s, files_h, defs)}




def get_present_path2(root_path, prefers):
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
    """获取指定路径下的所有目录"""
    paths = []
    for one in os.listdir(path):
        if os.path.isdir(path + "/" + one):
            paths.append(one)
    return paths


############################################################################################
#  TODO 这里一大串都不应该放在这里，需要提取到capture中比较合理
#  1. 关于日志的配置，结果的导出，配置的输入等 抽取到capture的main
#  2. 关键参数的识别，比如-DHAVE_CONFIG_H等，抽取为capture的一个function
#  3. CommandBuilder可以再创建一个文件，building_process还是保持为一个通用的模块
#  4. source_detective这里需要增加编译文件类型涵盖的返回，从而capture能判断需要使用什么编译
############################################################################################

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
        python program_name root_path [prefer_sub_folder1,prefer_sub_folder2,...] [outer_output_path]
""")
        sys.exit()

    if len(input_path) > 1 and input_path[-1] == '/':
        input_path = input_path[:-1]


    # 设置编译脚本输出目录和日志输出
    logger = parse_logger.getLogger("conf/logging.conf", \
            new_output=output_path + "/capture.log")
    command_output_path = input_path

    if output_path:
        command_output_path = output_path

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

    """
    # add Include path
    gcc_include_string = ""
    for path in sub_paths:
        gcc_include_string = gcc_include_string + " " + "-I" + path
    """

    compile_string = COMPILE_COMMAND

    logger.info("checking configure file...")
    is_has_configure = os.path.exists(input_path + "/configure")
    if is_has_configure:
        logger.info(input_path + "/configure" + " is exists.")
        compile_string += " -DHAVE_CONFIG_H"

    # 导出目录扫描数据
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

    # 单进程处理
    """
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
            makestring = compile_string + definition + " -c " + source_file + " -o " + output_file_path + gcc_include_string
            fout.write(makestring + "\n")
            commands.append(makestring)
    """

    command_builder = CommandBuilder(logger)
    command_builder.distribute_jobs(compile_string, command_output_path, \
            source_files, files_s_defs, [[] for i in source_files], sub_paths)
    result_dict = command_builder.run()

    logger.info("Dumping compiler commands complete")

    logger.info("Start dumping commands")
    # 导出生成的编译命令
    capture.dict_command_dump(command_output_path + "/compile_commands.json",
            result_dict)
    """
    capture.commands_dump(command_output_path + "/compile_commands.json",
            source_files,
            commands,
            [command_output_path for i in source_files]
            )
    """
    logger.info("Dumping commands success")

    logger.info("Complete")

