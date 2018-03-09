# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: macros_analysis.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-02-23 13:36:01
    @LastModif: 2018-02-23 13:36:01
    @Note:
"""

import sys
import os
import queue
import re
import capture.core.lexer_macros as lexer_macros
import subprocess


class MacrosAnalyzer(object):
    file_path = ""
    macros = {
        #key: macros_name
        #value: size(增加代码长度), {headers,}(条件编译内引入的额外头文件), {宏定义嵌套关系?}
    }
    filter_macros = []
    queue = queue.Queue()
    sub_paths = []
    sys_paths = []
    compiler_type = "C"

    def __init__(self, path=file_path, folders=sub_paths, sys_folders=sys_paths, compiler_type=compiler_type):
        if path:
            self.file_path = path

        if folders:
            self.sub_paths = folders

        if sys_folders:
            self.sys_paths = sys_folders

        if compiler_type:
            self.compiler_type = compiler_type
            if self.compiler_type == "C":
                cmd = 'echo | gcc -Wp,-v -x c - -fsyntax-only 2>&1 | grep "^\ /"'
            elif self.compiler_type == "CXX":
                cmd = 'echo | gcc -Wp,-v -x c++ - -fsyntax-only 2>&1 | grep "^\ /"'
            else:
                raise Exception("Unknown compiler type!")
            p = subprocess.Popen(cmd, shell=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out, err = p.communicate()
            lines = out.split()
            for line in lines:
                self.sys_paths.append(line.strip())

    def building_macros(self, file_path):
        filein = open(file_path, "r")
        pre_macros = []
        pre_nums = []

        # exclude macros for avoiding reinclude header
        globle_mark = True
        end_mark = False
        header_definition = None

        comment_mark = False
        tmp_line = ""

        for line in filein:
            line = tmp_line + " " + line.strip(" \t\n")
            line = re.sub(" +", " ", line)
            if line[-1] == '\\':
                tmp_line = line[:-1]
                continue
            elif re.match(r'.*/\*', line) and not re.match(r'.*/\*.*\*/', line) and not comment_mark:
                tmp_line = line
                comment_mark = True
                continue
            elif comment_mark and not re.match(".*\*/", line):
                tmp_line = line
                continue
            elif comment_mark and re.match(r'.*\*/', line):
                comment_mark = False
                tmp_line = ""
            else:
                tmp_line = ""
            if re.match("\s*#\s*if", line):
                result = lexer_macros.get_macros(line)
                if len(result) == 1 and globle_mark and re.match("\s*#\s*ifndef", line):
                    header_definition = result[0]
                    globle_mark = False
                else:
                    globle_mark = False
                num = 0
                if len(result) != 0:
                    for obj in result:
                        pre_macros.append(obj)
                        num += 1
                        if obj not in self.macros:
                            self.macros[obj] = []
                else:
                    pre_macros.append("")
                    num += 1
                pre_nums.append(num)
            elif re.match("\s*#\s*elif", line):
                pre_macros = pre_macros[:-(pre_nums[-1])]
                pre_nums = pre_nums[:-1]

                result = lexer_macros.get_macros(line)
                num = 0
                for obj in result:
                    pre_macros.append(obj)
                    num += 1
                    if obj not in self.macros:
                        self.macros[obj] = []
                pre_nums.append(num)
            elif re.match("\s*#\s*include\s*[\<\"](.*)[\>\"]", line):
                include_file_name = re.match("\s*#\s*include\s*[\<\"](.*)[\>\"]", line).group(1)
                if len(pre_macros) != 0:
                    for obj in pre_macros:
                        if obj:
                            self.macros[obj].append(include_file_name)
                else:
                    file_path = self._search_include(include_file_name)
                    if file_path:
                        self.queue.put(file_path)
            elif re.match("\s*#\s*endif", line):
                if len(pre_nums) == 1 and len(pre_macros) == 1:
                    if not end_mark:
                        end_mark = True
                    else:
                        header_definition = None
                pre_macros = pre_macros[:-(pre_nums[-1])]
                pre_nums = pre_nums[:-1]

        if end_mark and header_definition is not None:
            self.macros.pop(header_definition)
        filein.close()

    def _search_include(self, file_name, paths=None):
        """在项目环境下查找是否存在"""
        # TODO: 只在项目环境下查找,如果找到了，则说明需要读取，否则不管（系统头文件的关联起来就太多了）
        if paths is None:
            paths = self.sub_paths

        for sub_path in paths:
            file_path = sub_path + os.path.sep + file_name
            if os.path.exists(file_path):
                return file_path
        return None

    def _search_sys_include(self, file_name):
        paths = self.sys_paths + self.sub_paths
        return self._search_include(file_name, paths=paths)

    def start_building_macros(self):
        self.queue.put(self.file_path)
        self.macros = {}
        self.filter_macros = []

        while not self.queue.empty():
            self.building_macros(self.queue.get())

    def exclude_macros(self):
        """exclude some macros"""
        # TODO: 定制一些规则，可以将一些明确不会在当前系统环境下使用到的宏定义去除
        filter_includes = ["winsock2.h"]
        exclude_macros = [
            "__FreeBSD__",
            "__OpenBSD__",
            "__CYGWIN__",
            "__QNX__",
            "__GNUC__",
            "WIN32",
            "__WIN32__"
        ]

        filter_macros = set(exclude_macros)
        filter_set = set(filter_includes)
        self.filter_macros = self.macros.keys()
        for key, values in self.macros.iteritems():
            if key in filter_macros:
                self.filter_macros.remove(key)
                continue
            if len(values) == 0:
               self.filter_macros.remove(key)
            for header in values:
                if header in filter_set:
                    self.filter_macros.remove(key)
                    break
                if self._search_sys_include(header) is None:
                    # couldn't found macros include header
                    self.filter_macros.remove(key)
                    break
        line = ""
        for definition in self.filter_macros:
            line += " -D" + definition
        return line

    def build_definitions(self):
        """TODO: 可以定制一种方案讲比较高置信度的组合先返回，采用生成器的方法"""

    def dump_macros(self):
        import json
        print(json.dumps(self.macros, indent=2))

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
