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
comment_regex = re.compile(r"^#|^dnl")
message_regex = re.compile(r"^AC_MSG_NOTICE")
function_regex = re.compile(r"^([a-zA-Z_]+[a-zA-Z0-9_]*)$")

M4_MACROS_ARGS_COUNT = {
    # function_name, args_count
    "AC_DEFUN": ["default", "default"],
    "AC_MSG_CHECKING": ["str"],
    "AC_MSG_RESULT": ["str"],
    "AC_MSG_ERROR": ["str"],
    "AC_COMPILE_IFELSE": ["shell", "shell", "shell"],
    "AC_REQUIRE": ["name"]
}

AC_REGEX_RULES = (
    # 0. Comment line, or useless line
    # 1. The default global variable
    # 2. The output variable
    # 3. Conditional line
    # 4. Calling function line
    [1, macros_dir_regex, "macros_dir"],
    [1, header_regex, "header"],
    [2, subst_regex, "subst"],
    [4, function_regex, "function"],
    [0, comment_regex],
    [0, message_regex],
)

function_regex = re.compile(r"AC_DEFUN\(\)")
M4_REGEX_RULES = (
    [],
)

assignment_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*=\s*(.*)")
appendage_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*\+=\s*(.*)")

# remove [ -o ] witch maybe not present in Makefile.am flags
filename_flags = ["-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]


def _check_undefined(slices):
    for slice in slices:
        if re.search(r"\$\([a-zA-Z_][a-zA-Z0-9_]*\)", slice):
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


def dump_data(json_dict, output_path):
    import json
    with open(output_path, "w") as fout:
        json.dump(json_dict, fout, indent=4)


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

    def dump_makefile_am_info(self, output_path=None):
        if output_path:
            dump_data(self.makefile_am_info, output_path)
        else:
            dump_data(self.makefile_am_info, self._output_path + "/make_file_result.json")

    def _reading_makefile_am(self, am_pair_var, fhandle_am, options=[], is_in_reverse=[]):
        tmp_line = ""
        option_regexs = (
            (re.compile("if\s+(.*)"), "positive"),
            (re.compile("else"), "negative"),
            (re.compile("endif"), None),
        )
        for line in fhandle_am:
            # The \t on the left of the line has command line meaning
            line = tmp_line + " " + line.rstrip(" \t\n") if tmp_line else line.rstrip(" \t\n")
            line = re.sub(" +", " ", line)
            tmp_line = ""

            match = re.match("(.*)\s+#", line)
            if match:
                # Remove comment line
                line = match.group(1)

            if len(line) == 0:
                continue

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
                value = assig_match.group(2) if assig_match else append_match.group(2)

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

                present_option_dict = self._get_option_level_dict(am_pair_var[key], options, is_in_reverse,
                                                                  True if assig_match else False)
                present_option_dict["is_replace"] = True if assig_match else False
                present_option_dict["defined"] = present_option_dict["defined"] if append_match else []
                present_option_dict["undefined"] = present_option_dict["undefined"] if append_match else []

                temp = ""
                for (i, word) in enumerate(words):
                    # TODO: 针对与 @ARG@ 的类型，现在还没有出来，等明确了configure.ac解析顺序之后在解析还是怎么样
                    temp = temp + " " + word if temp else word
                    if i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-':
                        continue

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

                    temp = ""

            # Loading include Makefile.inc
            include_regex = re.compile("^include\s+(.*)")
            include_match = include_regex.match(line)
            if include_match:
                folder = os.path.sep.join(fhandle_am.name.split(os.path.sep)[:-1])
                include_path = folder + "/" + include_match.group(1)
                self._loading_include(am_pair_var, include_path, options, is_in_reverse)

    def _loading_include(self, am_pair_var, include_path, options, is_in_reverse):
        with open(include_path, "r") as include_fin:
            self._reading_makefile_am(am_pair_var, include_fin, options, is_in_reverse)

    def _check_global_dict_empty(self, dict):
        default_n_regex = re.compile(r"default_\d+")
        default_N = 1
        for option_key in dict["option"].iterkeys():
            if default_n_regex.match(option_key):
                default_N += 1
        if len(dict["defined"]) != 0 or len(dict["undefined"]) != 0 or len(dict["option"]) != 0:
            return True, default_N
        return False, 0

    def _get_option_level_dict(self, start_dict, options, is_in_reverse, is_assign):
        if len(options) == 0:
            return start_dict
        present_dict = start_dict
        has_default, default_N = self._check_global_dict_empty(present_dict)
        if len(options) == 0 and is_assign and has_default:
            # for default_N option, False will not be used.
            present_dict["option"]["default_" + default_N] = {
                True: {"defined": [], "undefined": [], "option": {}, "is_replace": True},
                False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
            }
        for option, reverse_stat in zip(options, is_in_reverse):
            if option not in present_dict["option"]:
                present_dict["option"][option] = {
                    True: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                    False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                }
            present_dict = present_dict["option"][option][not reverse_stat]
        return present_dict

    def _ac_match_check(self, line):
        for pair in AC_REGEX_RULES:
            match = pair[0].match(line)
            if match:
                self.configure_ac_info[pair[1]] = match.group(1)
                return True
        return False

    def set_configure_ac(self):
        config_file_name = self._check_configure_scan()
        if config_file_name:
            self._fhandle_configure_ac = open(config_file_name, "r")
        else:
            self._logger.warning("Not found configure.ac or configure.in file")
            return
        self.configure_ac_info = {
            "variables": {},
            # when program meet AC_SUBST, we will move variable from dict["variables"] to "export_variables" after
            # analysis.
            "export_variables": {},
            "conditionals": {
                # key: name of conditional witch will be use for Makefile.am conditionally compiling
                # value: {
                #   "option": {
                #       True:   ...
                #       False:  ...
                #    }
                # }
            }
        }
        ac_variables = self.configure_ac_info["variables"]

        try:
            self._load_configure_ac_info(ac_variables)
        except IOError:
            self._logger.warning("Couldn't read configure.ac file")

    def _load_configure_ac_info(self, ac_variables):
        # TODO: 针对与configure.ac 及其 m4 宏的解析
        # 1. 解析获得 m4 宏定义有哪些，构造一个引用函数表， ps: 对于搞不懂如何解析的部分直接跳过吧，不要强求
        # 2. 引用则查函数表，如果有则解析那部分的数据，或者是先解析完，这里是拷贝解析后的数据
        # 3. 关注的主要是：
        #    i. 赋值语句 重点关注的是被subst的变量和默认传递变量
        #   ii. AC_ARG_WITH 和 AC_ARG_ENABLE 关键是获取到default的方式, option的方式暂时不做详细,
        #       重点是关注这边导致的conditional变化
        #  iii. AC_SUBST

        if not self._fhandle_configure_ac:
            raise IOError("loading configure.ac or configure.in fail.")
        option_regexs = (
            re.compile(r"\s*if\s+test\s+")
        )

        for line in self._fhandle_configure_ac:
            line = line.strip(" \n\t")
            if self._ac_match_check(line):
                continue

            assign_match = assignment_regex.match(line)
            append_match = appendage_regex.match(line)
            if assign_match or append_match:
                key = assign_match.group(1) if assign_match else append_match.group(1)
                value = assign_match.group(2) if assign_match else append_match.group(2)
                if key not in ac_variables:
                    ac_variables[key] = {
                        "defined": [],
                        "undefined": [],
                        "is_replace": False,
                        "option": {}
                    }

    def _check_configure_scan(self):
        for file_name in CONFIGURE_AC_NAMES:
            file_path = self._project_path + os.path.sep + file_name
            if os.path.exists(file_path):
                return file_path
        return None

    def _preload_m4_config(self, configure_ac_filepath):
        cmd = "fgrep \"{}\" {}".format("AC_CONFIG_MACRO_DIR", configure_ac_filepath)
        p = subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, err = p.communicate()
        if p.returncode == 0:
            macros_dir_match = macros_dir_regex.match(out)
            if not macros_dir_match:
                self._logger.warning("Not match AC_CONFIG_MACRO_DIR in {}!".format(configure_ac_filepath))
                m4_folders = None
            else:
                m4_folders = macros_dir_match.group(1)
        else:
            self._logger.warning("cmd: {}, exec fail!".format(cmd))
            m4_folders = None
        return m4_folders

    def _get_m4_folder(self):
        if "macros_dir" not in self.configure_ac_info:
            config_file_name = self._check_configure_scan()
            if config_file_name:
                self._fhandle_configure_ac = open(config_file_name, "r")
                self.configure_ac_info["macros_dir"] = self._preload_m4_config(config_file_name)
            else:
                self._logger.warning("Not found configure.ac or configure.in file")
                return None

        return self.configure_ac_info["macros_dir"]

    def load_m4_macros(self):
        """Loading m4 files from m4 directory, and building up macros info table"""
        m4_folder_name = self._get_m4_folder()
        if not m4_folder_name:
            self._logger.warning("Not found m4 folder.")
            return

        m4_project = self._project_path + os.path.sep + m4_folder_name
        for file_name in os.listdir(m4_project):
            if not file_name.endswith(".m4"):
                continue
            file_path = m4_project + os.path.sep + file_name
            with open(file_path) as m4_fin:
                self._m4_file_analysis(m4_fin)

    def _m4_file_analysis(self, fin):
        """ *.m4 文件的分析，针对里面定义的宏定义，构建一份信息表"""
        import capture.utils.m4_macros_analysis as m4_macros_analysis
        lexer = m4_macros_analysis.M4Lexer()
        lexer.build()
        data = self._m4_block_reader(fin)
        self.m4_macros_info = {
            "function": {
                # key: function name
                # value: {
                #   key: variable name
                #   value: {defined:, undefined:, option:,}
                # }
            }
        }
        func_info = self.m4_macros_info["function"]
        func_pos = []
        quote_stacks = []
        quotes = (
            'LPAREN',
            'LSPAREN',
            'LBRACES',
            'RPAREN',
            'RSPAREN',
            'RBRACES',
        )
        squotes = (
            'LSPAREN',
            'RSPAREN',
        )
        len_quotes = len(quotes)

        analyze_type = "default"
        while len(data) != 0:
            for token in lexer.get_token_iter(data):
                if token.type == "AC_DEFUN":
                    func_info[token.value] = {}
                    func_pos.append((token.value, M4_MACROS_ARGS_COUNT[token.value]))

                if token.type in M4_MACROS_ARGS_COUNT:
                    func_pos.append((token.value, M4_MACROS_ARGS_COUNT[token.value]))

                # checking quote
                if token.type in quotes[:len_quotes / 2]:
                    quote_stacks.append(token.type)
                elif token.type in quote_stacks[len_quotes / 2:]:
                    quote = quote_stacks.pop()
                    if quotes[quotes.index(quote) + len_quotes / 2] != token.type:
                        self._logger.warning("Not match correct quote! Maybe be {} has some problem".format(fin.name))
                        return
                    if func_pos[-1][0] != "UNKNOWN" and token.type == "RSPAREN":
                        func_pos[-1][1] -= 1
                        analyze_type = M4_MACROS_ARGS_COUNT[func_pos[-1][0]][func_pos[-1][1]]




    def _m4_block_reader(self, fin, size=1024):
        """按行方式来逐步读取"""
        data = ""
        while size > 0:
            try:
                line = fin.next()
                size -= 1
            except StopIteration:
                self._logger.info("Reading file: {} complete".format(fin.name))
                break
            data += line
        return data


if __name__ == "__main__":
    if len(sys.argv) == 3:
        project_path = sys.argv[1]
        am_path = sys.argv[2]
    else:
        sys.stderr.write("Fail!\n")
        exit(-1)

    make_file_am = [
        am_path,
    ]
    import logging
    import logging.config
    logging.config.fileConfig("../conf/logging.conf")
    logger = logging.getLogger("captureExample")

    auto_tools_parser = AutoToolsParser(logger, project_path, "../../result")
    auto_tools_parser.set_makefile_am(make_file_am)
    auto_tools_parser.dump_makefile_am_info()

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
