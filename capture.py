# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: capture.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-23 11:27:56
    @LastModif: 2018-01-29 19:23:55
    @Note:
"""

import os
import sys
import re
import conf.parse_logger as parse_logger
import source_detective as source_detective
import building_process
import subprocess

import hashlib
import json

# 需要改为绝对路径
try:
    import redis
except ImportError:
    sys.path.append("./utils")
    import redis


# 基本配置项
DEFAULT_LOG_CONFIG_FILE = "conf/logging.conf"
DEFAULT_COMPILE_COMMAND = "gcc"

COMPILER_COMMAND_MAP = {
    "GNU": {
        "CXX": "g++",
        "C": "gcc"
    },
    "Clang": {
        "CXX": "clang++",
        "C": "clang"
    }
}


# 并发构建编译命令
class CommandBuilder(building_process.ProcessBuilder):
    def redis_setting(self, host="localhost", port=6379, db=0):
        self.redis_pool = redis.ConnectionPool(host=host, port=port, db=db)

    def basic_setting(self, compile_command, output_path):
        self.compile_command = compile_command
        self.output_path = output_path

    def mission(self, queue, result, locks=[]):
        lock = locks[0]
        pid = os.getpid()
        self._logger.info("Process pid:%d start." % pid)
        lock.acquire()
        while not queue.empty():
            job_dict = queue.get()
            lock.release()

            # build args
            directory = job_dict["exec_directory"]
            flag_string = ""
            for flag in job_dict["flags"]:
                flag_string += flag + " "
            definition_string = ""
            for definition in job_dict["definitions"]:
                if definition.find(r'=\"') != -1:
                    lst = re.split(r'\\"', definition)
                    if len(lst) > 2:
                        # 为空格添加转义符号
                        lst[1] = lst[1].replace(" ", "\ ")
                        definition = lst[0] + r"\"" + lst[1] + r"\""
                    else:
                        self._logger.warning("definition %s analysis error" % definition)
                definition_string += "-D" + definition + " "
            include_string = ""
            for include in job_dict["includes"]:
                include_string += "-I" + include + " "
            args_string = flag_string + definition_string + include_string

            sources = job_dict["source_files"]
            custom_flags = job_dict["custom_flags"]
            custom_definitions = job_dict["custom_definitions"]
            for i in range(len(sources)):
                src = sources[i]
                # custom
                custom_args_string = ""
                if i in custom_flags:
                    for flag in custom_flags[i]:
                        custom_args_string += flag + " "
                if i in custom_definitions:
                    for definition in custom_definitions[i]:
                        if definition.find(r'=\"') != -1:
                            lst = re.split(r'\\"', definition)
                            if len(lst) > 2:
                                # 为空格添加转义符号
                                lst[1] = lst[1].replace(" ", "\ ")
                                definition = lst[0] + r"\"" + lst[1] + r"\""
                            else:
                                self._logger.warning("custom definition %s analysis error" % definition)
                        custom_args_string += "-D" + definition + " "

                transfer_name = file_args_MD5Calc(src, \
                                      job_dict["flags"], job_dict["definitions"], job_dict["includes"], custom_args_string)
                output_command = self.compile_command[job_dict["compiler_type"]] + " "
                output_command += args_string
                output_command += custom_args_string
                output_command += "-c " + src + " "
                output_command += "-o " + self.output_path + "/" + transfer_name + ".o "

                json_dict = {
                    "directory": directory,
                    "file": src,
                    "command": output_command
                }
                result.append(json_dict)

            lock.acquire()
        lock.release()

        self._logger.info("Process pid:%d Complete." % pid)
        return


class CommandExec(building_process.ProcessBuilder):
    def mission(self, queue, result, locks=[]):

        lock = locks[0]
        pid = os.getpid()
        self._logger.info("Process pid:%d start." % pid)
        lock.acquire()
        while not queue.empty():
            job_dict = queue.get()
            lock.release()

            directory = job_dict["directory"]
            file = job_dict["file"]
            command = job_dict["command"]

            cmd = "cd %s" % directory + "; " + command

            p = subprocess.Popen(cmd, shell=True, \
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            # 可能会导致管道阻塞
            """
            retval = p.wait()
            sys.stdout.write("------ " + file + " --------\n" + p.stdout.read())

            if retval == 0:
                self._logger.info("compile: %s success" % file)
            else:
                self._logger.warning("compile: %s fail" % file)
            """
            # 推荐做法
            out, err = p.communicate()
            if out:
                sys.stdout.write("------ " + file + " --------\n" + out)
            else:
                sys.stdout.write("------ " + file + " --------\n")

            if p.returncode != 0:
                self._logger.warning("compile: %s fail" % file)
            else:
                self._logger.info("compile: %s success" % file)

            lock.acquire()
        lock.release()

        self._logger.info("Process pid:%d Complete." % pid)
        return


def bigFileMD5Calc(file):
    """逐步更新计算文件MD5"""
    m = hashlib.md5()
    buffer = 8192   # why is 8192 | 8192 is fast than 2048

    m.update(file)  # 加入文件的路径，使得不同目录即使文件内容相同，也能生成不同的MD5值
    with open(file, 'rb') as f:
        while True:
            chunk = f.read(buffer)
            if not chunk:
                break
            m.update(chunk)

    return m.hexdigest()


def fileMD5Calc(file):
    """直接读取计算文件MD5"""
    m = hashlib.md5()
    m.update(file)
    with open(file, 'rb') as f:
        m.update(f.read())

    return m.hexdigest()


def source_path_MD5Calc(file):
    """直接计算文件路径的MD5，不考虑文件内容，只要能对文件就行重新命令即可"""
    m = hashlib.md5()
    m.update(file)
    return m.hexdigest()


def file_transfer(filename, path):
    """文件名转换"""
    file = path + "/" + filename, "rb"
    statinfo = os.stat(file)
    if int(statinfo.st_size) / 1024 * 1024 >= 1:
        print "File size > 1M, use big file calc"
        return bigFileMD5Calc(file)
    return fileMD5Calc(file)


def file_args_MD5Calc(file, flags, definitions, includes, custom_arg):
    """
    文件可能被多次编译，因此需要用编译参数加到一起来标识一个目标
    :param file:
    :param flags:
    :param definitions:
    :param includes:
    :param custom_arg:
    :return:
    """
    m = hashlib.md5()
    m.update(file)

    args = (flags, definitions, includes)
    for configs in args:
        configs.sort()
        for line in configs:
            m.update(line)
    if custom_arg:
        m.update(custom_arg)
    return m.hexdigest()


def file_info_save(redis_instance, filename, source_path, transfer_name, definition, flags):
    """保存源文件信息到redis中"""
    seria_data = (source_path, filename, definition, flags)
    redis_instance.set(transfer_name, json.dumps(seria_data))
    return


def get_file_info(redis_instance, transfer_name):
    """利用transfer_name获取源文件编译信息
    Returns:
        source_path:    源文件路径
        filename:       文件名
        definition:     宏定义
        flags:          编译参数
    """
    raw_data = redis_instance.get(transfer_name)
    seria_data = json.loads(raw_data)
    return seria_data


def commands_dump(output_path, source_files, commands, working_paths):
    """导出生成的编译命令
    Args:
        output_path:        输出路径
        source_files:       源文件
        commands:           编译命令
        working_paths:      命令执行路径
    """
    json_body = []
    for output_tuple in zip(source_files, commands, working_paths):
        json_data = {
                "directory": output_tuple[2],
                "command": output_tuple[1],
                "file": output_tuple[0]
                }
        json_body.append(json_data)
    with open(output_path, 'w') as fout:
        json.dump(json_body, fout, indent=4)
    return


def dict_command_dump(output_path, result_dict, output_script=True):
    """利用最终返回的结果字典，导出生成的编译命令"""
    json_body = []
    index = len(output_path.split("/")[-1]) + 1
    script_output_path = output_path[:-index]
    if output_script:
        fout = open(script_output_path + "/compile.sh", "w")
    while len(result_dict):
        key, output_tuple = result_dict.popitem()
        json_data = {
                "directory": output_tuple[2],
                "command": output_tuple[1],
                "file": output_tuple[0]
                }
        json_body.append(json_data)
        if output_script:
            fout.write(output_tuple[1] + "\n")

    if output_script:
        fout.close()

    with open(output_path, 'w') as fout:
        json.dump(json_body, fout, indent=4)
    return


def scan_data_dump(output_path, source_files, macros, include_files, \
        include_paths, is_has_config=False):
    """导出目录扫描数据
    Args:
        output_path:        输出路径
        source_files:       源文件
        macros:             宏定义(与源文件一一对应)
        include_files:      头文件
        include_paths:      系统头文件搜索路径
        is_has_config:      是否含有configure
    """
    if is_has_config:
        map_macros = map(lambda macro: macro + " -DHAVE_CONFIG_H", macros)
    else:
        map_macros = macros

    json_data = {
            "source_files": source_files,
            "macros": map_macros,
            "source_count": len(source_files),
            "include_files": include_files,
            "include_count": len(include_files),
            "include_paths": include_paths
            }

    with open(output_path, 'w') as fout:
        json.dump(json_data, fout, indent=4)
    return


class CaptureBuilder(object):
    """主要的编译构建脚本生成类"""
    def __init__(self, logger, \
                 root_path,
                 output_path=None,
                 build_type="cmake",
                 build_path=None,
                 prefers = [],
                 compiler_type=DEFAULT_COMPILE_COMMAND, \
                 compiler_path=None):
        self.__prefers = prefers
        self.__root_path = os.path.abspath(root_path)
        self.compiler_type = compiler_type
        self.__build_type = build_type
        self.__build_path = build_path
        self._logger = logger

        if output_path:
            self.__output_path = os.path.abspath(output_path)
        else:
            self.__output_path = self.__root_path

        # 设置编译器
        if compiler_path:
            self.compiler_path = compiler_path
        else:
            self.compiler_path = get_system_compiler_path(compiler_type)

    def add_prefer_folder(self, folder):
        self.__prefers.append(folder)
        pass

    @property
    def build_type(self):
        return self.__build_type

    @property
    def root_path(self):
        return self.__root_path

    @property
    def prefers(self):
        return self.__prefers

    @prefers.setter
    def prefers(self, prefers):
        import types
        if type(prefers) == types.ListType:
            self.__prefers = prefers
        else:
            raise TypeError("object 'prefers' is not ListType")

    def scan_project(self):
        """
        扫描项目文件，获取项目统计信息，并保留扫描结果，用于构建编译命令
        :return:            project_scan_result     =>      json
        """
        source_infos = []
        self._logger.info("Start Scaning project folders...")
        if self.__build_type == "cmake":
            if not self.__build_path:
                self.__build_path = self.__root_path + "/build"
            source_infos, include_files, files_count = \
               source_detective.get_present_path_cmake(self.__root_path, self.__prefers, self.__build_path)
        elif self.__build_type == "make":   # TODO: 添加普通项目的Makefile解析
            sub_paths, files_s, files_h, files_s_defs = \
                source_detective.get_present_path_autotools(self.__root_path, self.__prefers)
            gcc_string = "gcc"

            # is_has_configure = os.path.exists(self.__root_path + "/configure")
            # if is_has_configure:
            gcc_string += " -DHAVE_CONFIG_H"

            gcc_include_string = ""
            for path in sub_paths:
                gcc_include_string = gcc_include_string + " " + "-I" + path

            source_files = [x[0] for x in files_s]
            commands = []
            with open(self.__output_path + "/" + "my_compile.sh", "w+") as fout:
                for source_file_tuple, definition in zip(files_s, files_s_defs):
                    source_file = source_file_tuple[0]
                    suffix = source_file.split(".")[-1]
                    index = -(len(suffix))
                    file_name = source_file.split("/")[-1]
                    file_index = -(len(file_name) + 1)
                    output_path_str = self.__output_path
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
            commands_dump(self.__output_path + "/compile_commands.json",
                          source_files,
                          commands,
                          [self.__output_path for i in source_files]
                        )
            return [], [], []

            pass
        else:   # 连Makefile都没有，直接构建
            """
            TODO: 扫描用Makefile直接构建的项目
                1. 先获取所有的源文件, 头文件
                2. 根据源文件去获取对应的目标文件是怎产生的,
                    (1) make -d -n -k, 其中-n是为不实际执行make, 然后将输出的文本进行检索,构建出所依赖的变量
                    (2) 写入伪目标到Makefile中, 伪目标的操作主要是打印我们需要的参数值
                    (3) 获取返回值, 解析这些返回值
                3. 根据截获的参数构建出源文件的编译命令
            """
            paths, files_s, files_h = \
                source_detective.get_present_path_make(self.__root_path, self.__prefers)
            pass
        self._logger.info("End of Scaning project folders...")

        # Test
        fout = open("test.out", "w")
        json.dump(source_infos, fout, indent=4)
        return source_infos, include_files, files_count

    def command_prebuild(self, source_infos, files_count, compiler_id="GNU"):
        # if len(source_infos) > 100 and files_count > 5000:
            # 只有任务比较多的时候，构建才需要并行化
        command_builder = CommandBuilder(self._logger)
        command_builder.distribute_jobs(source_infos)
        # setting
        command_builder.basic_setting(COMPILER_COMMAND_MAP[compiler_id], self.__output_path)
        command_builder.redis_setting()
        result_list = command_builder.run()
        fout = open("result.json", "w")
        output_list = []
        while len(result_list):
            json_ob = result_list.pop()
            output_list.append(json_ob)
        json.dump(output_list, fout, indent=4)
        self.command_exec(output_list)

    def command_exec(self, output_list):
        command_exec = CommandExec(self._logger)
        command_exec.distribute_jobs(output_list)
        command_exec.run()
        return


def get_system_compiler_path(compiler_type):
    """获取系统自带的编译器路径"""
    a = 10
    pass


def parse_prefer_str(prefer_str, input_path):
    if prefer_str == "":
        prefers = []
    elif prefer_str == "all":
        prefers = source_detective.get_directions(input_path)
    else:
        prefers = prefer_str.strip(' \n\t').split(",")
    return prefers


def main():
    """主要逻辑"""
    # TODO: 使用比较简洁一点的参数输入方式
    output_path = ""
    prefers_str = ""
    make_type = "cmake"
    cmake_build_path = ""
    compiler_id = None
    if len(sys.argv) == 2:
        input_path = sys.argv[1]
    elif len(sys.argv) == 3:
        input_path = sys.argv[1]
        prefers_str = sys.argv[2]
    elif len(sys.argv) == 4:
        # 增加了输出目录
        input_path = sys.argv[1]
        prefers_str = sys.argv[2]
        output_path = sys.argv[3]
    elif len(sys.argv) == 5:
        input_path = sys.argv[1]
        prefers_str = sys.argv[2]
        output_path = sys.argv[3]
        make_type = sys.argv[4]
    elif len(sys.argv) == 6:
        input_path = sys.argv[1]
        prefers_str = sys.argv[2]
        output_path = sys.argv[3]
        make_type = sys.argv[4]
        cmake_build_path = sys.argv[5]
    elif len(sys.argv) == 7:
        input_path = sys.argv[1]
        prefers_str = sys.argv[2]
        output_path = sys.argv[3]
        make_type = sys.argv[4]
        cmake_build_path = sys.argv[5]
        compiler_id = sys.argv[6]
    else:
        sys.stderr.write(
    """Please input project root path to compiler.
    Usage:
        python program_name root_path [prefer_sub_folder1,prefer_sub_folder2,...] [outer_output_path] [build_type] [build_path] [compiler_id]
        
    compiler_id = ["GNU", "Clang"]
""")
        sys.exit(-1)

    if len(input_path) > 1 and input_path[-1] == '/':
        input_path = input_path[:-1]

    # TODO 可能需要添加为参数输入
    config_file = DEFAULT_LOG_CONFIG_FILE
    logger = parse_logger.getLogger(config_file, new_output="capture.log")

    # command_output_path = input_path
    # if output_path:
    #     command_output_path = output_path
    #     logger.info("output_path is None, set output path: %s" % input_path)

    # 获取关注目录
    prefers = parse_prefer_str(prefers_str, input_path)
    logger.info("prefer directories: %s" % str(prefers))

    # CaptureBuilder
    capture_builder = CaptureBuilder(logger, input_path, output_path, \
                                     prefers=prefers, build_type=make_type, build_path=cmake_build_path)
    source_infos, include_files, files_count = capture_builder.scan_project()

    # 暂时不编译违背cmake 定义的源文件
    if compiler_id:
        if compiler_id not in COMPILER_COMMAND_MAP:
            sys.stderr.write("No such compiler_id!")
        capture_builder.command_prebuild(source_infos[:-2], files_count, compiler_id)
    capture_builder.command_prebuild(source_infos[:-2], files_count)


if __name__ == "__main__":
    main()


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
