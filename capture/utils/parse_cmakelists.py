# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_cmakelists.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-19 12:06:16
    @LastModif: 2018-03-19 12:07:24
    @Note: This parser is used to parse original CMakeLists.txt, and build up compile commands flags.
"""
import os
import sys
import re
import copy
import logging

if __name__ == "__main__":
    import capture_util
    import cmake_command_analyzer
    sys.path.append("../conf")
    import parse_logger
    parse_logger.addFileHandler("./capture.log", "capture")
else:
    import capture.utils.capture_util as capture_util
    import capture.utils.cmake_command_analyzer as cmake_command_analyzer

# from capture.utils.cmake_command_analyzer import *


logger = logging.getLogger("capture")


default_module_paths = [
    "CMake",
    "cmake"
]


def add_defined_value(var_dict, variable, value, options, reverses):
    if variable not in var_dict:
        var_dict[variable] = {
            "defined": [],
            "undefined": [],
            "option": {},
            "is_replaces": False
        }
    option_dict = cmake_command_analyzer.get_option_level(var_dict.get(variable, dict()),
                                                          options, reverses)
    option_dict["defined"].append(value)
    return


def get_relative_build_path(path, project_path, cmake_build_path):
    abs_project_path = os.path.abspath(project_path)
    abs_present_path = os.path.abspath(path)
    relative_path = abs_present_path[len(abs_project_path):]
    present_build_path = cmake_build_path + relative_path
    return present_build_path


class CMakeParser(object):
    __sample_result = {
        "variables": dict(),
        "list_variables": dict(),
        "target": {
            "libcurl": dict()
        },
        # Use to storage set_property scope variables, except target scope
        "scope_target": dict(),
        # global definitions， can be passed to subdirecotries
        "definitions": {
            "defined": [],
            "undefined": [],
            "option": {},
            "is_replace": False,        # always False
        },
        "includes": {
            "defined": [],
            "undefined": [],
            "option": {},
            "is_replace": False,        # always False
        },
        "flags": {
            "defined": [],
            "undefined": [],
            "option": {},
            "is_replace": False,        # always False
        },
        # This field is used to storage option config for generating config.h file.
        "config_option": dict()
    }
    cmake_commands = [
        "set",
        "list",
        "if",
        "elseif",
        "else",
        "endif",
        "set_property",
        "set_target_properties",
        "option",
        "add_library",
        "add_executable",
        "target_include_directories",
        "add_definitions",
        "include_directories",
    ]

    def __init__(self, project_path, output_path, build_path=None):
        self._project_path = project_path
        self._output_path = output_path
        if build_path is None:
            self._build_path = os.path.join(self._output_path, "build")
            if not os.path.exists(self._build_path):
                os.makedirs(self._build_path)
        self._cmake_module_path = [os.path.join(self._project_path, folder) for folder in default_module_paths]

        self._cmake_info = {}

        # Build commands regex
        self.cmake_commands.sort(key=len, reverse=True)
        command_name_patterns = map(lambda command: cmake_command_analyzer.get_command_name_pattern(command),
                                    self.cmake_commands)
        command_pattern = "|".join(command_name_patterns)
        self.command_regex = re.compile(command_pattern)

    def _add_default_value(self, cmakelist_path):
        """
            This function will add some default value for cmake analyzer, like
            CMAKE_SOURCE_PATH, CMAKE_BINARY_PATH, CMAKE_MODULE_PATH and etc.

            TODO: 1. add default CMAKE_MODULE_PATH,
                  2. add CMAKE compiler and linker variables.
        """
        self._cmake_info[cmakelist_path] = copy.deepcopy(self.__sample_result)
        cmake_current_path = os.path.dirname(cmakelist_path)
        if not os.path.isabs(cmake_current_path):
            cmake_current_path = os.path.join(self._project_path, cmake_current_path)
        cmake_binary_current_path = get_relative_build_path(cmake_current_path, self._project_path,
                                                            self._build_path)
        one_cmake_info = self._cmake_info.get(cmakelist_path, self.__sample_result)
        var_dict = one_cmake_info.get("variables", dict())

        add_defined_value(var_dict, "CMAKE_SOURCE_DIR", self._project_path, list(), list())
        add_defined_value(var_dict, "CMAKE_CURRENT_SOURCE_DIR", cmake_current_path, list(), list())
        add_defined_value(var_dict, "CMAKE_BINARY_DIR", self._build_path, list(), list())
        add_defined_value(var_dict, "CMAKE_CURRENT_BINARY_DIR", cmake_binary_current_path, list(), list())
        return

    def dump_cmake_info(self):
        import json
        with open(os.path.join(self._output_path, "cmake_info.json"), "w") as fout:
            json.dump(self._cmake_info, fout, indent=4)

    def loading_cmakelists(self, cmakelist_path):
        """Loading CMakeLists.txt or *.cmake files"""
        if not os.path.exists(cmakelist_path):
            return False
        with open(cmakelist_path, "r") as cmake_fin:
            data = cmake_fin.read()
            data = data.lstrip(" \t\n")
        cmake_path = os.path.dirname(cmakelist_path)
        if not os.path.isabs(cmake_path):
            cmake_path = os.path.join(self._project_path, cmake_path)

        one_cmake_info = self._cmake_info.get(cmakelist_path, self.__sample_result)
        options = list()
        reverses = list()
        for command_name, args_line in cmake_command_analyzer.get_cmake_command(data, cmake_path, one_cmake_info):
            logger.debug(command_name)
            if not self.command_regex.match(command_name + "("):
                # pass commands we don't care about
                continue
            analyzer = cmake_command_analyzer.get_command_analyzer(command_name)
            analyzer(args_line, one_cmake_info, options, reverses)
        logger.info("Stop analyzing CMakeLists: %s." % cmakelist_path)
        return


if __name__ == "__main__":
    if len(sys.argv) == 3:
        project_path = sys.argv[1]
        filename = sys.argv[2]
    else:
        sys.stderr.write("Error, without filename.\n")
        sys.exit(-1)

    cmake_parser = CMakeParser(project_path, "../../result")
    cmake_parser.loading_cmakelists(filename)
    cmake_parser.dump_cmake_info()

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
