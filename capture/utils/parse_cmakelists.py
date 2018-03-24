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
import re
import logging

from capture.utils.cmake_command_analyzer import *


logger = logging.getLogger("capture")


default_module_paths = [
    "CMake",
    "cmake"
]

cmake_field_definitions = {
    #TODO: function选项的需要去调用解析函数，一般的则采用通用的来做
    # set 还有其他参数，但是我们不需要关注, 要保证 CACHE 去除
    # value_list 可以为0 或 多个， 如果是 0 表示，置空变量， 如果是多个值，则通过 ; 分隔
    "set": set_analyzer,
    # list的结构有很多种情况
    "list": list_analyzer,
    "include": ["string"]
}
comment_regex = re.compile(r"#.*?\n(.*)", flags=re.DOTALL)
pattern_list = map("{}\(\s*(.*?)\s*\)(.*)".format, cmake_field_definitions.keys())
regex_list = map(lambda pattern: re.compile(pattern, flags=re.DOTALL), pattern_list)


class CMakeParser(object):
    def __init__(self, project_path, output_path):
        self._project_path = project_path
        self._output_path = output_path
        self._cmake_module_path = [os.path.join(self._project_path, folder) for folder in default_module_paths]

        self._cmake_infos = {}

    def cmake_module_set(self, module_name, cmake_module_path=None):
        """Loading CMake modules from cmake module"""
        if isinstance(cmake_module_path, str) and cmake_module_path not in self._cmake_module_path:
            self._cmake_module_path.append(cmake_module_path)

        for module_path in self._cmake_module_path:
            cmake_file_path = os.path.join(self._project_path, module_path)
            if os.path.exists(cmake_file_path):
                return self.loading_cmakelists(cmake_file_path)
            else:
                continue
        logger.warning("Not found module: %s." % module_name)
        return False

    def loading_cmakelists(self, cmake_list_path):
        """Loading CMakeLists.txt or *.cmake files"""

        if not os.path.exists(cmake_list_path):
            return False
        cmake_fin = open(cmake_list_path, "r")
        data = cmake_fin.read()



        cmake_fin.flush()
        cmake_fin.close()




# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
