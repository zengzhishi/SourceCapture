# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: cmake_command_analyzer.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-24 21:05:23
    @LastModif: 2018-03-24 21:17:10
    @Note: Define some cmake commands analyzer here.
"""
import re
import capture.utils.capture_util as capture_util
from capture.utils.m4_macros_analysis import check_one_undefined_slice, check_undefined
from capture.utils.m4_macros_analysis import check_one_undefined_slice_self, check_undefined_self

# set_cache_type = ["BOOL", "FILEPATH", "PATH", "STRING", "INTERNAL"]

var_pattern = r"[a-zA-Z_][a-zA-Z0-9_]*"
env_pattern = r"ENV{" + var_pattern + r"}"
docstring_pattern = r"\"[^\\\"]\""                 # exclude \"
var_value_pattern = r"\$\(" + var_pattern + r"\)"

value_without_quote_pattern = r"[^ \t\n\)]+"
value_with_quote_pattern = docstring_pattern
filename_flags = ["-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]


# 1. Argument config command
def set_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variable", dict())
    list_var_dict = result.get("list_variable", dict())

    # 1. variable
    # TODO: consider whether we need a env_variable dict
    variable_regex = re.compile("\s*(" + var_pattern + ")\s+(.*)")
    variable_match = variable_regex.match(match_args_line)
    env_regex = re.compile("\s*ENV{(" + var_pattern + ")}\s+(.*)")
    env_match = env_regex.match(match_args_line)
    if not variable_match and not env_match:
        raise capture_util.ParserError("Set pattern error in set({}).".format(match_args_line))

    if variable_match:
        variable_name = variable_match.group(1)
        match_line = variable_match.group(2)
    else:
        variable_name = env_match.group(1)
        match_line = env_match.group(2)

    # 2. value
    words = capture_util.split_line(match_line)
    if len(words) == 0:
        # unset variable
        pass
    elif len(words) == 1 or len(words) > 1 and re.match(r"CACHE", words[1]):
        # one elem config
        value_line = words[0]
        value_line = capture_util.strip_quotes(value_line)

        temp = ""
        values = capture_util.split_line(value_line)
        for (i, word) in enumerate(values):
            temp = temp + " " + word if temp else word
            if i != len(values) - 1 and word in filename_flags and values[i + 1][0] != '-':
                continue

            value_with_quote_match = re.match(r"\"([^\\\"])\"", temp)
            if value_with_quote_match:
                value = value_with_quote_match.group(1)
            else:
                value = word
            slices = capture_util.undefined_split(value, var_dict)

            transfer_word = "".join(slices)
            # TODO: 暂时无法表达 string 拼接操作
            if check_undefined(slices, with_ac_var=False):
                if check_undefined_self(slices, variable_name):
                    if len(slices) == 1:
                        var_dict["is_replace"] = False
                    temp = ""
                    continue
                var_dict["undefined"].append(transfer_word)
            else:
                var_dict["defined"].append(transfer_word)
            temp = ""
    elif len(words) > 1 and not re.match(r"CACHE", words[1]):
        # list config
        value_list = list_var_dict.get("value", list())
        for (i, value_line) in enumerate(words):
            if re.match(r"CACHE", words[i]):
                break
            value_line = capture_util.strip_quotes(value_line)

            temp = ""
            values = capture_util.split_line(value_line)
            var_dict = {
                "defined": [],
                "undefined": [],
            }
            for (i, word) in enumerate(values):
                temp = temp + " " + word if temp else word
                if i != len(values) - 1 and word in filename_flags and values[i + 1][0] != '-':
                    continue

                value_with_quote_match = re.match(r"\"([^\\\"])\"", temp)
                if value_with_quote_match:
                    value = value_with_quote_match.group(1)
                else:
                    value = word

                slices = capture_util.undefined_split(value, var_dict)
                transfer_word = "".join(slices)

                # TODO: 暂时无法表达 string 拼接操作
                if check_undefined(slices, with_ac_var=False):
                    if check_undefined_self(slices, variable_name):
                        if len(slices) == 1:
                            var_dict["is_replace"] = False
                        temp = ""
                        continue
                    var_dict["undefined"].append(transfer_word)
                else:
                    var_dict["defined"].append(transfer_word)
                temp = ""
        pass


def list_analyzer(match_args_line, result, option, reverse):
    pass


# 2. include
def include_directories_analyzer(match_args_line, result, option, reverse):
    pass


# other config command
def set_target_properties_analyzer(match_args_line, result, option, reverse):
    pass


def transform_makefile_inc_analyzer(match_args_line, result, options, reverses):
    pass

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
