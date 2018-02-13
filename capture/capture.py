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
import source_detective
import building_process
import subprocess
import ConfigParser

import hashlib
import json
import copy

# 需要改为绝对路径
try:
    import redis
except ImportError:
    sys.path.append("./utils")
    import redis


# 基本配置项
DEFAULT_CONFIG_FILE = "conf/capture.cfg"
DEFAULT_COMPILER_ID = "GNU"
DEFAULT_BUILDING_TYPE = "make"


def load_compiler(config, compiler_map):
    compiler_ids = config.get("Compiler", "compiler_id").split(",")
    c_compilers = config.get("Compiler", "c_compiler").split(",")
    cxx_compilers = config.get("Compiler", "cxx_compiler").split(",")
    for compiler_id, c_compiler, cxx_compiler in zip(compiler_ids, c_compilers, cxx_compilers):
        compiler_map[compiler_id] = {
            "CXX": cxx_compiler,
            "C": c_compiler
        }
    return compiler_map, compiler_map[compiler_ids[0]]["CXX"]


COMPILER_COMMAND_MAP = {}
config = ConfigParser.ConfigParser()
config.read(DEFAULT_CONFIG_FILE)
DEFAULT_LOG_CONFIG_FILE = config.get("Default", "logging_config")
COMPILER_COMMAND_MAP, DEFAULT_COMPILE_COMMAND = load_compiler(config, COMPILER_COMMAND_MAP)


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
            sys.stdout.write(" CC Building {}\n{}".format(file, out))
            # if out:
            #     sys.stdout.write(" CC Building {}\n{}".format(file, out))
            # else:
            #     sys.stdout.write("------ " + file + " --------\n")

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


def commands_dump(output_path, compile_commands):
    """导出生成的编译命令
    Args:
        output_path:            输出路径
        compile_commands:       最终生成的compile_commands.json文件所需要的数据
    """
    with open(output_path, 'w') as fout:
        json.dump(compile_commands, fout, indent=4)
    return


def scan_data_dump(output_path, scan_data, compile_commands=None, saving_to_db=False):
    """
    导出目录扫描数据,可能需要导出到redis中
    :param output_path:             输出路径
    :param scan_data:               项目扫描数据
    :param compile_commands:
    :param saving_to_db:            是否需要保存到redis
    :return:
    """

    if saving_to_db:
        pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
        redis_instance = redis.Redis(connection_pool=pool)
        for parse in scan_data:
            compiler_confs = {
                "includes": parse["includes"],
                "definitions": parse["definitions"],
                "compiler_type": parse["compiler_type"],
                "config_from": parse["config_from"],
                "exec_directory": parse["exec_directory"],
                "flags": parse["flags"]
            }
            for i, file in enumerate(parse["source_files"]):
                custom_flags = parse[i]
                custom_definitions = parse[i]
                custom_confs = copy.deepcopy(compiler_confs)
                custom_confs["definitions"].extend(custom_definitions)
                custom_confs["flags"].extend(custom_flags)
                custom_confs["file"] = file
                saving_json_line = json.dumps(custom_confs)
                # TODO：这里是错误的做法，应该是hash之后的文件名作为key
                redis_instance.set(file, saving_json_line)

    with open(output_path, 'w') as fout:
        json.dump(scan_data, fout, indent=4)
    return


class CaptureBuilder(object):
    """主要的编译构建脚本生成类"""
    def __init__(self, logger, \
                 root_path,
                 output_path=None,
                 build_type=DEFAULT_BUILDING_TYPE,
                 build_path=None,
                 prefers=None,
                 compiler_id=None):
        if prefers:
            self.__prefers = prefers
        else:
            self.__prefers = []
        self.__root_path = os.path.abspath(root_path)
        self.__build_type = build_type
        self.__build_path = build_path
        self._logger = logger

        if output_path:
            self.__output_path = os.path.abspath(output_path)
        else:
            self.__output_path = self.__root_path

        if compiler_id is None:
            self.__compiler_id = compiler_id
        else:
            self.__compiler_id = DEFAULT_COMPILER_ID


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
        elif self.__build_type == "make":
            # TODO: make 项目构建，只要生成了Makefile就能使用的方法(只针对编译，不针对链接以及其他工作)
            # scan project files
            sub_paths, files_s, files_h, compile_db = \
                source_detective.get_present_path_make(self._logger, self.__root_path,
                                                       self.__prefers, self.__build_path,
                                                       self.__output_path)

            include_files = files_h
            files_count = len(files_s)
            source_infos = []
            # get make prebuild command
            for command_info in compile_db:
                source_file = command_info["file"]
                flags = command_info["arguments"]

                # exclude prebuilded source files from project total sources
                try:
                    files_s.remove(source_file)
                except ValueError:
                    self._logger.warning("file: %s not found, project scan error!" % (source_file))

                includes = filter(lambda flag: True if flag[:2] == "-I" else False, flags)
                final_includes = map(lambda flag: flag[2:] if flag[2] != ' ' else flag[3:], includes)

                definitions = filter(lambda flag: True if flag[:2] == "-D" else False, flags)
                final_definitions = map(lambda flag: flag[2:] if flag[2] != ' ' else flag[3:], definitions)

                final_flags = filter(lambda flag: True if flag[:2] != "-I" and flag[:2] != "-D" else False, flags)

                file_infos = {
                    "source_files": [source_file,],
                    "definitions": list(final_definitions),
                    "includes": list(final_includes),
                    "flags": list(final_flags),
                    "exec_directory": command_info["directory"],
                    "compiler_type": command_info["compiler"],
                    # 考虑是否可以不加，没必要
                    "custom_flags": [],
                    "custom_definitions": [],
                    "config_from": []
                }
                source_infos.append(file_infos)

            # use sub_paths to build up globle includes, and get system includes
            # build up command for left source files
            global_includes = map(lambda path: os.path.abspath(path), sub_paths)
            c_files = filter(lambda file_name: True if file_name.split(".")[-1] == "c" else False, files_s)
            cpp_files = filter(lambda file_name: True if file_name.split(".")[-1] in ["cxx", "cpp", "cc"] else False, files_s)
            c_file_infos = {
                "source_files": c_files,
                "includes": list(global_includes),
                "definitions": [],
                "flags": ["-g", "-fPIC"],
                "exec_directory": self.__build_path if self.__build_path else self.__root_path,
                "compiler_type": "C",
                "custom_flags": [],
                "custom_definitions": [],
                "config_from": []
            }
            cxx_file_infos = copy.deepcopy(c_file_infos)
            cxx_file_infos["source_files"] = cpp_files
            cxx_file_infos["compiler_type"] = "CXX"
            # TODO: 这里可能需要从其他那里获取
            cxx_file_infos["flags"].append("-std=c++14")
            source_infos.append(c_file_infos)
            source_infos.append(cxx_file_infos)

        else:   # 连Makefile都没有，直接构建
            sub_paths, files_s, files_h = source_detective.get_present_path(self.__root_path, self.__prefers)
            include_files = files_h
            files_count = len(files_s)
            global_includes = map(lambda path: os.path.abspath(path.replace(' ', "_")), sub_paths)
            #global_includes = map(lambda path: os.path.abspath(path.replace('(', "")), global_includes)
            #global_includes = map(lambda path: os.path.abspath(path.replace(')', "")), global_includes)
            c_files = filter(lambda file_name: True if file_name.split(".")[-1] == "c" else False, files_s)
            cpp_files = filter(lambda file_name: True if file_name.split(".")[-1] in ["cxx", "cpp", "cc"] else False, files_s)

            is_has_configure = os.path.exists(self.__root_path + "/configure")
            definitions = []
            if is_has_configure:
                definitions.append("HAVE_CONFIG_H")
            c_file_infos = {
                "source_files": c_files,
                "includes": list(global_includes),
                "definitions": definitions,
                "flags": ["-g", "-fPIC"],
                "exec_directory": self.__build_path if self.__build_path else self.__root_path,
                "compiler_type": "C",
                "custom_flags": [],
                "custom_definitions": [],
                "config_from": []
            }
            cxx_file_infos = copy.deepcopy(c_file_infos)
            cxx_file_infos["source_files"] = cpp_files
            cxx_file_infos["compiler_type"] = "CXX"
            # TODO: 这里可能需要从其他那里获取
            cxx_file_infos["flags"].append("-std=c++14")
            source_infos.append(c_file_infos)
            source_infos.append(cxx_file_infos)

        self._logger.info("End of Scaning project folders...")

        # dumping data
        scan_data_dump(self.__output_path + "/project_scan_result.json", source_infos)
        return source_infos, include_files, files_count

    def command_prebuild(self, source_infos, files_count):
        # if len(source_infos) > 100 and files_count > 5000:
            # 只有任务比较多的时候，构建才需要并行化
        command_builder = CommandBuilder(self._logger)
        command_builder.distribute_jobs(source_infos)
        # setting
        command_builder.basic_setting(COMPILER_COMMAND_MAP[self.__compiler_id], self.__output_path)
        command_builder.redis_setting()
        result_list = command_builder.run()

        output_list = []
        while len(result_list):
            json_ob = result_list.pop()
            output_list.append(json_ob)

        commands_dump(self.__output_path + "/compile_commands.json", output_list)
        return output_list

    def command_exec(self, output_list):
        command_exec = CommandExec(self._logger)
        command_exec.distribute_jobs(output_list)
        command_exec.run()
        return


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

    if compiler_id not in COMPILER_COMMAND_MAP:
        sys.stderr.write("No such compiler_id!")
        compiler_id = None

    # CaptureBuilder
    capture_builder = CaptureBuilder(logger, input_path, output_path, compiler_id=compiler_id,
                                     prefers=prefers, build_type=make_type, build_path=cmake_build_path)
    source_infos, include_files, files_count = capture_builder.scan_project()
    logger.info("all files: %d, all includes: %d" % (files_count, len(include_files)))

    # 暂时不编译cmake和Makefile未定义的源文件
    if make_type in ["cmake", "make"]:
        result = capture_builder.command_prebuild(source_infos[:-2], files_count)
    else:
        result = capture_builder.command_prebuild(source_infos, files_count)
    capture_builder.command_exec(result)


if __name__ == "__main__":
    main()


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent