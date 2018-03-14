#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import queue
import configparser

import capture.utils.parse_cmake as parse_cmake
import capture.utils.parse_make as parse_make
import capture.utils.parse_scons as parse_scons

import capture.utils.capture_util as capture_util

import logging
logger = logging.getLogger("capture")

DEFAULT_CONFIG_FILE = os.path.join("capture", "conf", "capture.cfg")

# suffix config loading
config = configparser.ConfigParser()
config.read(DEFAULT_CONFIG_FILE)

DEFAULT_FLAGS = config.get("Default", "default_flags").split()
DEFAULT_MACROS = config.get("Default", "default_macros").split(",")
DEFAULT_CXX_FLAGS = config.get("Default", "default_cxx_flags").split()

c_file_suffix_str = config.get("Default", "source_c_suffix")
cxx_file_suffix_str = config.get("Default", "source_cxx_suffix")

c_file_suffix = set(c_file_suffix_str.split(","))
cxx_file_suffix = set(cxx_file_suffix_str.split(","))
source_file_suffix = c_file_suffix | cxx_file_suffix
include_file_suffix = set(config.get("Default", "include_suffix").split(","))

VERBOSE_LIST = config.get("SCons", "verbose").split(',')


def get_system_path(compiler):
    """
    Acquire GCC system headers path
    """
    # Checking c system headers
    cmd = "echo 'main(){}' | " + compiler + " -E -x c -v -"
    # Checking c++ system headers
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
    paths = []
    for one in os.listdir(path):
        if os.path.isdir(os.path.join(path, one)):
            paths.append(one)
    return paths


# cmake project with building temp files
def using_cmake(path, output_path, cmake_build_args=""):
    """
    :param path:                        project path
    :param output_path:
    :param cmake_build_args:
    :return:
        status:                         Checking and execution result
        build_path:                     cmake outer_build path
    """
    filename = os.path.join(path, "CMakeLists.txt")
    if not os.path.exists(filename):
        return False, None

    build_folder_path = os.path.join(output_path, "build")
    if not os.path.exists(build_folder_path):
        os.makedirs(build_folder_path)
    else:
        shutil.rmtree(build_folder_path)
        os.makedirs(build_folder_path)

    cmd = "cmake {} {}".format(path, cmake_build_args)
    (returncode, out, err) = capture_util.subproces_calling(cmd, cwd=build_folder_path)

    if returncode == 0:
        return True, build_folder_path

    return False, None


def check_cmake(path, project_path, cmake_build_path):
    """
    Checking whether there is exist CMakeLists.txt
    :param path:
    :return:        bool
    """
    #check CMakeList.txt is exist
    if not cmake_build_path:
        cmake_build_path = project_path
    present_build_path = get_relative_build_path(path, project_path, cmake_build_path)
    if os.path.exists(os.path.join(path, "CMakeLists.txt")) \
            and os.path.exists(os.path.join(present_build_path, "CMakeFiles")):
        return True
    return False


def check_cmake_exec_dest_dirname(file_name):
    """
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
    infos["flags"] = DEFAULT_FLAGS
    infos["definitions"] = DEFAULT_MACROS
    return


# autotools project
def using_autotools(path, output_path, configure_args=""):
    filename = os.path.join(path, "configure")
    if not os.path.exists(filename):
        return False, None

    build_folder_path = os.path.join(output_path, "build")
    if not os.path.exists(build_folder_path):
        os.makedirs(build_folder_path)
    else:
        shutil.rmtree(build_folder_path)
        os.makedirs(build_folder_path)

    cmd = "{} {}".format(filename, configure_args)
    (returncode, out, err) = capture_util.subproces_calling(cmd, cwd=build_folder_path)

    if returncode == 0:
        return True, build_folder_path

    return False, None


def get_definitions(path):
    """Simply get macros from Makefile.am"""
    cmd = "grep \"^AM_CPPFLAGS*\" " + path + "/Makefile.am | awk '{print $3}'"
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    retval = p.wait()
    definitions = []
    for line in p.stdout.readlines():
        if line[1] == 'D':
            definitions.append(line.strip())
    return definitions


def autotools_project_walk(root_path, prefers):
    to_walks = queue.Queue()

    definitions = get_definitions(root_path)
    to_walks.put((root_path, definitions))

    prefer_paths = set()
    for name in prefers:
        file_path = os.path.join(root_path, name)
        prefer_paths.add(file_path)

    level = 0
    while not to_walks.empty():
        (present_path, old_definitions) = to_walks.get()
        definitions = get_definitions(present_path)
        def_str = ""
        print("\tscan path:" + present_path)

        if len(definitions) == 0:
            definitions = old_definitions

        for def_s in definitions:
            def_str += " " + def_s

        filelists = os.listdir(present_path)
        files = []
        for file_name in filelists:
            file_path = os.path.join(present_path, file_name)
            if os.path.isdir(file_path):
                if not level:
                    if file_path in prefer_paths:
                        to_walks.put((file_path, definitions))
                else:
                    if file_name[0] != '.':                         # exclude hidden file.
                        to_walks.put((file_path, definitions))
            else:
                files.append(file_name)
        level = 1
        yield (present_path, files, def_str)


def get_present_path_autotools(root_path, prefers):
    """
    Iterate all project folder and return project scan info
    Args:
        root_path:
        prefers:            The top level folder will be scan.

    Returns:
        sub_paths:          Using in building -I flags
        source_files:
        include_files:
        source_defs:        Macros
    """
    if len(prefers) == 0:
        prefers = ["src", "include", "lib", "modules"]

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
                    output_name_prefix = folder[root_path_length + 1:].replace(os.path.sep, "_")
                    files_s.append((os.path.join(folder, file_name), output_name_prefix))
                    files_s_defs.append(definition)
                elif suffix in include_file_suffix:
                    files_h.append(os.path.join(folder, file_name))
    return paths, files_s, files_h, files_s_defs


# GNU make project
def using_make(path):
    try:
        is_exist = parse_make.check_makefile(path)
    except IOError:
        return False, None

    if is_exist:
        return True, path
    else:
        return False, None


# SCons project
def using_scons(path):
    is_exist = parse_scons.check_sconstruct_exist(path)
    if is_exist:
        return True, path
    return False, None


class AnalyzerError(Exception):
    def __init__(self, message=None):
        if message:
            self.args = (message,)
        else:
            self.args = ("Analyzer Error happen!",)


class Analyzer(object):
    def __init__(self, root_path, output_path, prefers, build_path=None):
        self._project_path = root_path
        self._output_path = output_path
        self._prefers = prefers
        self._build_path = build_path if build_path else self._project_path

    def selective_walk(self):
        """Scan project and return present_path and files"""
        to_walks = queue.Queue()

        to_walks.put(self._project_path)

        prefer_paths = set()
        for name in self._prefers:
            file_path = os.path.join(self._project_path, name)
            prefer_paths.add(file_path)

        level = 0
        while not to_walks.empty():
            present_path = to_walks.get()
            logger.info("\tscan path: %s" % present_path)

            files = []
            for file_name in os.listdir(present_path):
                file_path = os.path.join(present_path, file_name)
                if os.path.isdir(file_path):
                    if not level:
                        if file_path in prefer_paths:
                            to_walks.put(file_path)
                    else:
                        if file_name[0] != '.':                         # Exclude hidden files
                            to_walks.put(file_path)
                else:
                    files.append(file_name)
            level = 1
            yield (present_path, files)

    def get_project_infos(self):
        paths = []
        files_s = []
        files_h = []
        for line_tulpe in self.selective_walk():
            folder = line_tulpe[0]
            file_paths = line_tulpe[1]
            paths.append(folder)
            for file_path in file_paths:
                slice = file_path.split('.')
                suffix = slice[-1]
                if len(slice) > 1:
                    if suffix in source_file_suffix:
                        files_s.append(os.path.join(folder, file_path))
                    elif suffix in include_file_suffix:
                        files_h.append(os.path.join(folder, file_path))
        return paths, files_s, files_h


class SConsAnalyzer(Analyzer):
    def get_project_infos_scons(self, build_args=None):
        paths, files_s, files_h = self.get_project_infos()
        if not self._output_path:
            try:
                import tempfile
                output = tempfile.TemporaryFile()
            except ImportError:
                logger.warning("Can't create temporary file.")
                raise AnalyzerError("Can't create temporary file.")
        else:
            output = open(os.path.join(self._output_path, "scons_infos.txt"), "w+")

        if build_args:
            output = parse_scons.create_command_infos(self._build_path, output,
                                                      VERBOSE_LIST, build_args=build_args)
        else:
            output = parse_scons.create_command_infos(self._build_path, output, VERBOSE_LIST)
        if not output:
            raise AnalyzerError("Without SConstruct in project.")
        output.flush()
        output.seek(0)
        line_count, skip_count, compile_db = parse_scons.parse_flags(output, self._build_path)
        output.close()
        logger.info("Parse scons building result: [line_count: %d] [skip_count: %d]" %
                    (line_count, skip_count))
        return paths, files_s, files_h, compile_db


class MakeAnalyzer(Analyzer):
    def get_project_infos_make(self, build_args=None):
        paths, files_s, files_h = self.get_project_infos()
        if not self._output_path:
            try:
                import tempfile
                output = tempfile.TemporaryFile()
            except ImportError:
                logger.warning("Can't create temporary file.")
                raise AnalyzerError("Can't create temporary file.")
        else:
            output = open(os.path.join(self._output_path, "make_infos.txt"), "w+")

        if build_args:
            output = parse_make.create_command_infos(self._build_path, output, make_args=build_args)
        else:
            output = parse_make.create_command_infos(self._build_path, output)

        if not output:
            raise AnalyzerError("Not found Makefile in project.")
        output.flush()
        output.seek(0)

        line_count, skip_count, compile_db = parse_make.parse_flags(output, self._build_path)
        output.close()
        logger.info("Parse make building result: [line_count: %d] [skip_count: %d]" %
                    (line_count, skip_count))

        return paths, files_s, files_h, compile_db


class CMakeAnalyzer(Analyzer):
    def get_cmake_info(self, present_path):
        """
        Searching project given, and analyzing CMakeFiles to strip compiler flags.

        :param present_path:                            present searching path.
        :return:
        """
        present_build_path = present_path
        if self._build_path:
            final_build_path = self._build_path
        else:
            final_build_path = self._project_path
        present_build_path = get_relative_build_path(present_path, self._project_path, final_build_path)
        cmake_files_path = os.path.join(present_build_path, "CMakeFiles")
        info_list = []

        def _get_abs_path(path):
            if os.path.isabs(path[0]):
                return path
            return os.path.abspath(os.path.join(final_build_path, path))

        for file_name in os.listdir(cmake_files_path):
            file_path = os.path.join(cmake_files_path, file_name)
            if os.path.isdir(file_path) and check_cmake_exec_dest_dirname(file_name):
                # 目标目录
                flags_file = os.path.join(file_path, "flags.make")
                depend_file = os.path.join(file_path, "DependInfo.cmake")
                if os.path.exists(flags_file) and os.path.exists(depend_file):
                    cmake_infos = parse_cmake.parse_cmakeInfo(depend_file)
                    origin_flags, origin_custom_flags, origin_custom_definitions = parse_cmake.parse_flags(flags_file)
                    for [depend_files, definitions, includes, compiler_type], flags in zip(cmake_infos, origin_flags):
                        includes = map(lambda relative_path: _get_abs_path(relative_path), includes)
                        custom_flags = {}
                        custom_definitions = {}
                        depend_s_files = list(filter(lambda file: file[-2:] != ".o", depend_files))
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
                            "source_files": list(depend_s_files),
                            "flags": flags,
                            "definitions": definitions,
                            "includes": list(includes),
                            "compiler_type": compiler_type,
                            "custom_flags": custom_flags,
                            "custom_definitions": custom_definitions
                        })

        # 对于有定义CMakeLists.txt文件，但是没有配置编译选项的情况
        # For those sources without config.
        if len(info_list) == 0:
            info_list.append({
                "source_files": [],
                "flags": [],
                "definitions": [],
                "includes": [],
                "compiler_type": ""
            })
        return info_list

    def selective_walk(self):
        """
        Searching in root_project_path, and return scan result dict.
        :return:    [present_path, files_s_infos, files_h]
            files_s_infos -> list
            files_s_infos = [[files_s, flags, defs, includes, exec_path], ...]
        """
        to_walks = queue.Queue()
        to_walks.put(self._project_path)
        # Mark sources have been compiled
        used_file_s_set = set()
        # Add all includes for compiling undefined source
        include_set = set()
        # Add prefer folders
        prefer_paths = set()
        for name in self._prefers:
            file_path = os.path.join(self._project_path, name)
            prefer_paths.add(file_path)

        level = 0
        other_file_s = []
        while not to_walks.empty():
            present_path = to_walks.get()
            if check_cmake(present_path, self._project_path, self._build_path):
                logger.info("\tscan path: %s" % present_path)
                info_list = self.get_cmake_info(present_path)
                if self._build_path:
                    exec_path = self._build_path
                else:
                    exec_path = self._project_path

                # update
                for data_dict in info_list:
                    for file in data_dict.get("source_files", []):
                        used_file_s_set.add(file)
                    for include in data_dict.get("includes", []):
                        include_set.add(include)
                    data_dict["exec_directory"] = exec_path
                    data_dict["config_from"] = present_path
                yield info_list

            for file_name in os.listdir(present_path):
                file_path = os.path.abspath(os.path.join(present_path, file_name))
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

        # Build up undefined sources list
        undefind_files = []
        for file_path in other_file_s:
            if file_path not in used_file_s_set:
                undefind_files.append(file_path)

        includes = list(include_set)
        undefind_info_list = [{
            "source_files": undefind_files,
            "flags": [],
            "definitions": [],
            "includes": includes,
            "exec_directory": self._project_path,
            "compiler_type": "",
            "custom_flags": [],
            "custom_definitions": [],
        }]
        yield undefind_info_list

    def get_project_infos(self):
        if len(self._prefers) == 0:
            self._prefers = ["src", "include", "lib", "modules"]

        source_infos = []
        files_count = 0
        include_files = []
        cxx_files_info = {
            "source_files": [],
            "exec_directory": self._project_path,
            "compiler_type": "CXX",
            "flags": DEFAULT_CXX_FLAGS,
            "custom_flags": [],
            "custom_definitions": [],
        }
        for info_list in self.selective_walk():
            info_list = list(info_list)
            for info in info_list:
                if len(list(info.get("source_files", []))) == 0:
                    continue
                # Empty compiler_type is the undefined info list.
                compiler_type = info.get("compiler_type")
                if not compiler_type:
                    set_default(info)
                    cxx_files_info["flags"].extend(info.get("flags", []))
                    cxx_files_info["definitions"] = info.get("definitions", [])
                    cxx_files_info["includes"] = info.get("includes", [])
                    lefts_s = []
                    source_files = info.get("source_files", [])
                    for file in source_files:
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
                    files_count += len(info.get("source_files", []))
                source_infos.append(info)
        if len(cxx_files_info["source_files"]):
            source_infos.append(cxx_files_info)

        return source_infos, include_files, files_count
