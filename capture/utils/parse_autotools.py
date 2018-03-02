# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_autotools.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-01 16:50:58
    @LastModif: 2018-03-01 16:50:58
    @Note: TODO: Analyze autotools config files.
"""

import subprocess
import os
import sys
import re


CONFIGURE_AC_NAMES = (
    "configure.ac",
    "configure.in"
)

macros_dir_regex = re.compile(r'^AC_CONFIG_MACRO_DIR\(\[(.*)\]\)')
header_regex = re.compile(r"AC_CONFIG_HEADERS\((.*)\)")
subst_regex = re.compile(r"AC_SUBST\((.*)\)")

REGEX_RULES = (
    [1, macros_dir_regex, "macros_dir"],
    [1, header_regex, "header"],
    [1, subst_regex, "subst"],
)

assignment_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*=\s*(.*)")
appendage_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*\+=\s*(.*)")


def _check_undefined(slices):
    for slice in slices:
        if re.match("$\([a-zA-Z_][a-zA-Z0-9_]*\)", slice):
            return True
    return False


def unbalanced_quotes(s):
    single = 0
    double = 0
    for c in s:
        if c == "'":
            single += 1
        elif c == '"':
            double += 1

    is_half_quote = single % 2 == 1 or double % 2 == 1
    return is_half_quote


def split_line(line):
    # Pass 1: split line using whitespace
    words = line.strip().split()
    # Pass 2: merge words so that the no. of quotes is balanced
    res = []
    for w in words:
        if len(res) > 0 and unbalanced_quotes(res[-1]):
            res[-1] += " " + w
        else:
            res.append(w)
    return res


class AutoToolsParser(object):
    _fhandle_configure_ac = None
    # _fhandle_makefile_am = {}
    configure_ac_info = {}
    m4_macros_info = {}
    makefile_am_info = {}

    def __init__(self, logger, project_path, output_path, build_path=None):
        self._logger = logger
        self._project_path = project_path
        self._output_path = output_path

        self._build_path = build_path if build_path else self._project_path

    def __del__(self):
        if self._fhandle_configure_ac:
            self._fhandle_configure_ac.close()

    @property
    def build_path(self):
        return self._build_path

    @property
    def project_path(self):
        return self._project_path

    def set_makefile_am(self, project_scan_result):
        """
        TODO: 将source_detective扫描到的Makefile.am，或Makefile.in文件输入进来
        :param project_scan_result:                     project scan result
        :return:
        """
        for file_path in project_scan_result:
            fhandle_am = open(file_path, "r")
            self.makefile_am_info[file_path] = {
                "variables": {},
                "destinations": {}
            }
            am_pair_var = self.makefile_am_info[file_path]["variables"]
            am_pair_dest = self.makefile_am_info[file_path]["destinations"]

            self._reading_makefile_am(am_pair_var, fhandle_am)
            fhandle_am.close()
        return

    def _reading_makefile_am(self, am_pair_var, fhandle_am, options=[], is_in_reverse=[]):
        tmp_line = ""
        option_regexs = (
            (re.compile("if\s+(.*)"), "positive"),
            (re.compile("else"), "negative"),
            (re.compile("endif"), None),
        )
        for line in fhandle_am:
            # The \t on the left of the line has command line meaning
            line = tmp_line + " " + line.rstrip(" \t\n")
            line = re.sub(" +", " ", line)
            tmp_line = ""

            match = re.match("(.*)\s+#", line)
            if match:
                # Remove comment line
                line = match.group(1)

            if line[-1] == '\\':
                tmp_line = line[:-1]
                continue

            # Checking option status, to build option flags
            for option_regex, action in option_regexs:
                match = option_regex.match(line)
                if match:
                    if action is None:
                        options = options[:-1]
                        is_in_reverse = is_in_reverse[:-1]
                    elif action == "positive":
                        options.append(match.group(1))
                        is_in_reverse.append(False)
                    else:
                        is_in_reverse[-1] = True

            # Checking assignment
            assig_match = assignment_regex.match(line)
            append_match = appendage_regex.match(line)
            if assig_match or append_match:
                key = assig_match.group(1) if assig_match else append_match.group(1)
                value = assig_match.group(2) if assig_match else append_match.group(1)

                if key not in am_pair_var:
                    # TODO: 如果是在全局变量的一次替换，将创建一个名称为 "default_N" 的option来存储（N可以用来存储多个,多次更改）
                    am_pair_var[key] = {
                        "defined": [],
                        "undefined": [],
                        "is_replace": False,  # 表示在这一级将做一个替换, 第一级默认为False，default_N必定为True
                        "option": {}
                    }

                words = split_line(value)
                with_var_line_regex = re.compile(r"(.*)\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)(.*)")

                present_option_dict = self._get_option_level_dict(am_pair_var[key], options, is_in_reverse)
                present_option_dict["is_replace"] = True if assig_match else False
                present_option_dict["defined"] = present_option_dict["defined"] if append_match else []
                present_option_dict["undefined"] = present_option_dict["undefined"] if append_match else []

                for word in words:
                    temp = word
                    with_var_line_match = with_var_line_regex.match(temp)
                    # slices will be a reversed list
                    slices = []
                    while with_var_line_match:
                        temp = with_var_line_match.group(1)
                        undefine_var = with_var_line_match.group(2)
                        other = with_var_line_match.group(3)
                        if undefine_var in am_pair_var:
                            value = am_pair_var[undefine_var]
                            if len(value["undefined"]) == 0 and value["option"] is None:
                                undefine_var = " ".join(value["defined"]) if len(value["defined"]) != 0 else ""
                                temp = temp + undefine_var + other
                            elif value["option"] is None:
                                slices.append(other)
                                slices.append(value["defined"])
                                slices.append(value["undefined"])
                            else:
                                slices.append(other)
                                slices.append("$({})".format(undefine_var))
                        with_var_line_match = with_var_line_regex.match(temp)
                    slices.append(temp)
                    slices.reverse()
                    transfer_word = "".join(slices)
                    # 获取当前的option状态
                    if _check_undefined(slices):
                        present_option_dict["undefined"].append(transfer_word)
                    else:
                        present_option_dict["defined"].append(transfer_word)

            # Loading include Makefile.inc
            include_regex = re.compile("^include\s+(.*)")
            include_match = include_regex.match(line)
            if include_match:
                include_path = include_match.group(1)
                self._loading_include(am_pair_var, include_path, options, is_in_reverse)

    def _loading_include(self, am_pair_var, include_path, options, is_in_reverse):
        with open(include_path, "r") as include_fin:
            self._reading_makefile_am(am_pair_var, include_fin, options, is_in_reverse)

    def _get_option_level_dict(self, start_dict, options, is_in_reverse):
        if len(options) == 0:
            return start_dict
        present_dict = start_dict
        for option, reverse_stat in zip(options, is_in_reverse):
            if option not in present_dict["option"]:
                present_dict["option"][option] = {
                    True: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                    False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                }
            present_dict = present_dict["option"][option][reverse_stat]
        return present_dict

    def match_check(self, line):
        for pair in REGEX_RULES:
            match = pair[0].match(line)
            if match:
                self.configure_ac_info[pair[1]] = match.group(1)
                return True
        return False

    def load_configure_ac_info(self):
        if not self._fhandle_configure_ac:
            raise IOError("loading configure.ac or configure.in fail.")

        for line in self._fhandle_configure_ac:
            line = line.strip(" \n\t")
            if self.match_check(line):
                continue
            # Output variables for Makefile.am
            assignment_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)=(.*)")
            match = assignment_regex.match(line)
            if match:
                value = assignment_regex.match(line).group(2)
                key = assignment_regex.match(line).group(1)

    def check_configure_scan(self):
        for file_name in CONFIGURE_AC_NAMES:
            file_path = self._project_path + os.path.sep + file_name
            if os.path.exists(file_path):
                return file_path
        return None

    def get_m4_folder(self):
        if "macros_dir" not in self.configure_ac_info:
            config_file_name = self.check_configure_scan()
            if config_file_name:
                self._fhandle_configure_ac = open(config_file_name, "r")
                try:
                    self.load_configure_ac_info()
                except IOError:
                    self._logger.warning("Loading configure.ac fail.")
                    return None
            else:
                self._logger.warning("Not found configure.ac or configure.in file")
                return None

        return self.configure_ac_info["macros_dir"]

    def load_m4_macros(self):
        """Loading m4 files from m4 directory, and building up macros info table"""
        m4_project = self._project_path + os.path.sep + self.get_m4_folder()
        for file_name in os.listdir(m4_project):
            if not file_name.endswith(".m4"):
                continue
            file_path = m4_project + os.path.sep + file_name
            with open(file_path) as m4_fin:
                self.m4_file_analysis(m4_fin)

    def m4_file_analysis(self, fin):
        """ *.m4 文件的分析，针对里面定义的宏定义，构建一份信息表"""
        pass


def getter_function(name):
    def getvalue(autotools_parser):
        return getattr(autotools_parser, name)
    return getvalue


AS_VALUES = {
    "top_builddir": getter_function("get_build_path"),
    "src_builddir": getter_function("get_project_path"),
}


def parse_autotools_project():
    pass


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
