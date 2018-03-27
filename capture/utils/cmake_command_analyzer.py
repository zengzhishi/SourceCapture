# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: cmake_command_analyzer.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-24 21:05:23
    @LastModif: 2018-03-24 21:17:10
    @Note: Define some cmake commands analyzer here.
    TODO: 缺少对cmake-generator-expression的解析, 这部分应该是可以做出来的，只是可能语法识别比较繁琐, 暂时先不完成
"""
import re
import sys
import logging

if __name__ == "__main__":
    import capture_util
    sys.path.append("../conf")
    import parse_logger
    parse_logger.addFileHandler("./capture.log", "capture")
#     from m4_macros_analysis import check_undefined, check_one_undefined_slice
#     from m4_macros_analysis import check_undefined_self, check_one_undefined_slice_self
else:
    import capture.utils.capture_util as capture_util
#     from capture.utils.m4_macros_analysis import check_one_undefined_slice, check_undefined
#     from capture.utils.m4_macros_analysis import check_one_undefined_slice_self, check_undefined_self

logger = logging.getLogger("capture")


def check_one_undefined_slice(slice, with_ac_var=False):
    undefined_pattern = r"\$[a-zA-Z_][a-zA-Z0-9_]*|\$[\{\(][a-zA-Z_][a-zA-Z0-9_]*[\)\}]"
    undefined_at_pattern = r"\@[a-zA-Z_][a-zA-Z0-9_]*\@"
    if with_ac_var:
        undefined_pattern = undefined_pattern + r"|" + undefined_at_pattern

    undefined_regex = re.compile(undefined_pattern)

    if undefined_regex.search(slice):
        return True


def check_undefined(slices, with_ac_var=False):
    """Checking whether slices has undefined variables."""
    for slice in slices:
        if check_one_undefined_slice(slice, with_ac_var):
            return True
    return False


def check_one_undefined_slice_self(slice, self_var):
    search = re.search(r"\$\(?([a-zA-Z_][a-zA-Z0-9_]*)\)?", slice)
    if search:
        append_var = search.group(1)
        if append_var == self_var:
            return True
    return False


def check_undefined_self(slices, self_var):
    """Checking undefined slices whether contain itself variables."""
    for slice in slices:
        if check_one_undefined_slice_self(slice, self_var):
            return True
    return False


# set_cache_type = ["BOOL", "FILEPATH", "PATH", "STRING", "INTERNAL"]
var_pattern = r"[a-zA-Z_][a-zA-Z0-9_]*"
env_pattern = r"ENV{" + var_pattern + r"}"
docstring_pattern = r"\"[^\\\"]\""                 # exclude \"
var_value_pattern = r"\$\(" + var_pattern + r"\)"

value_without_quote_pattern = r"[^ \t\n\)]+"
value_with_quote_pattern = docstring_pattern
filename_flags = ["-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]

prefer_target_properties = [
    "COMPILE_DEFINITIONS",      # Add definitions for source compiling. Using the syntax VAR or VAR=value.
    # Function-style definitions are not supported.
    "COMPILE_FLAGS",            # compile_definitions finally will add to compile_flags and pass preprocessor.
    "COMPILE_OPTIONS",          # just like COMPILE_FLAGS.
    "HAS_CXX",                  # Force a target to use the CXX linker
    "LINKER_LANGUAGE",          # What tool to use for linking, based on language.
    "LINK_FLAGS",               # flags to use when linking this target.
    "LINK_INTERFACE_LIBRARIES", # List public interface libraries for a shared library or executable.
    "LINK_DEPENDS",             # Additional files on which a target binary depends for linking.
    "STATIC_LIBRARY_FLAGS",     # Extra flags to use when linking static libraries.
    "TYPE",                     # The type of the target, STATIC_LIBRARY, MODULE_LIBRARY, SHARED_LIBRARY,
    # EXECUTABLE or one of the internal target types.
    "CXX_EXTENSIONS",           # Boolean specifying whether compiler specific extensions are requested.
    "CXX_STANDARD",             # The C++ standard whose features are requested to build this target.
    # Will add -std=gnu++XX, Supported values are 98, 11 and 14.
    "C_EXTENSIONS",
    "C_STANDARD",
]
target_properties_set = set()
with open("cmake_target_properties.txt", "r") as fin:
    for line in fin:
        target_properties_set.add(line.strip("\n"))


def get_option_level(start_dict, options, reverses, is_list=False):
    """Get the present option level var_dict."""
    if len(options) == 0:
        return start_dict
    present_dict = start_dict
    for option, reverse_stat in zip(options, reverses):
        if option not in present_dict["option"]:
            if is_list:
                present_dict["option"][option] = {
                    True: {"items": [], "option": {}, "is_replace": False},
                    False: {"items": [], "option": {}, "is_replace": False},
                }
            else:
                present_dict["option"][option] = {
                    True: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                    False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                }
        present_dict = present_dict["option"][option][not reverse_stat]
    return present_dict


def get_variable_dict(variable_name, result, options, reverses, is_list=False):
    var_dict = result.get("variables", dict())
    list_var_dict = result.get("list_variables", dict())
    if not is_list:
        if variable_name not in var_dict:
            var_dict[variable_name] = {
                "defined": [],
                "undefined": [],
                "option": {},
                "is_replace": False,
            }
        value_var_dcit = var_dict.get(variable_name, dict())
        option_dict = get_option_level(value_var_dcit, options, reverses)
    else:
        if variable_name not in list_var_dict:
            list_var_dict[variable_name] = {
                "items": [],
                "option": {},
                "is_replace": False
            }
        value_list_dict = list_var_dict.get(variable_name, dict())
        option_dict = get_option_level(value_list_dict, options, reverses, is_list=True)
    return option_dict


def get_target_dict(target_property, target, options, reverses):
    print(target_property)
    if target_property not in target:
        target[target_property] = {
            "defined": [],
            "undefined": [],
            "option": {},
            "is_replace": False
        }
    value_var_dict = target.get(target_property, dict())
    option_dict = get_option_level(value_var_dict, options, reverses)
    return option_dict


# 1. Argument config command
def set_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variables", dict())
    list_var_dict = result.get("list_variables", dict())

    # 1. variable
    # TODO: consider whether we need a env_variable dict
    variable_regex = re.compile("\s*(" + var_pattern + ")\s+(.*)", flags=re.DOTALL)
    variable_match = variable_regex.match(match_args_line)
    env_regex = re.compile("\s*ENV{(" + var_pattern + ")}\s+(.*)", flags=re.DOTALL)
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
        if variable_name not in var_dict:
            var_dict[variable_name] = {
                "defined": [],
                "undefined": [],
                "option": {},
                "is_replace": False,
            }
        value_var_dcit = var_dict.get(variable_name, dict())
        option_dict = get_option_level(value_var_dcit, options, reverses)
        # If without self var, set action will be a replace action
        option_dict["is_replace"] = True
        option_dict["defined"] = []
        option_dict["undefined"] = []

    elif len(words) == 1 or len(words) > 1 and re.match(r"CACHE", words[1]):
        # one elem config
        value_line = words[0]
        value_line = capture_util.strip_quotes(value_line)
        if variable_name not in var_dict:
            var_dict[variable_name] = {
                "defined": [],
                "undefined": [],
                "option": {},
                "is_replace": False,
            }

        value_var_dcit = var_dict.get(variable_name, dict())
        option_dict = get_option_level(value_var_dcit, options, reverses)
        # If without self var, set action will be a replace action
        option_dict["is_replace"] = True

        temp = ""
        values = capture_util.split_line(value_line)
        for (i, word) in enumerate(values):
            temp = temp + " " + word if temp else word
            if i != len(values) - 1 and word in filename_flags and values[i + 1][0] != '-':
                continue

            value_with_quote_match = re.match(r"\"([^\\\"])\"", temp, flags=re.DOTALL)
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
                        option_dict["is_replace"] = False
                    temp = ""
                    continue
                option_dict["undefined"].append(transfer_word)
            else:
                option_dict["defined"].append(transfer_word)
            temp = ""

    elif len(words) > 1 and not re.match(r"CACHE", words[1]):
        # list config
        if variable_name not in list_var_dict:
            list_var_dict[variable_name] = {
                "items": [],
                "option": {},
                "is_replace": False
            }
        value_list_dict = list_var_dict.get(variable_name, dict())
        option_dict = get_option_level(value_list_dict, options, reverses, is_list=True)
        # Use Set() to add element to list, will replace value
        option_dict["is_replace"] = True
        value_list = option_dict.get("items", list())
        for (i, value_line) in enumerate(words):
            if re.match(r"CACHE", words[i]):
                break
            value_line = capture_util.strip_quotes(value_line)
            var_dict = {
                "defined": [],
                "undefined": [],
            }

            temp = ""
            values = capture_util.split_line(value_line)
            for (i, word) in enumerate(values):
                temp = temp + " " + word if temp else word
                if i != len(values) - 1 and word in filename_flags and values[i + 1][0] != '-':
                    continue

                value_with_quote_match = re.match(r"\"([^\\\"]*)\"", temp, flags=re.DOTALL)
                if value_with_quote_match:
                    value = value_with_quote_match.group(1)
                else:
                    value = word

                # TODO: Here we just replace a simple single value var, ignore list var replaces.
                slices = capture_util.undefined_split(value, var_dict)
                transfer_word = "".join(slices)

                if check_undefined(slices, with_ac_var=False):
                    var_dict["undefined"].append(transfer_word)
                else:
                    var_dict["defined"].append(transfer_word)
                temp = ""
            value_list.append(var_dict)


def list_analyzer(match_args_line, result, options, reverses):
    words = capture_util.split_line(match_args_line)
    if len(words) < 2:
        raise capture_util.ParserError("List command contend analyze error! [%s]" % match_args_line)
    action = words[0]
    variable_name = words[1]
    var_list_dict = get_variable_dict(variable_name, result, options, reverses, is_list=True)

    # inner function define
    def list_length(args):
        if len(args) != 1:
            raise capture_util.ParserError("List LENGTH action analysis error!")

        if var_list_dict.get("is_replace", False):
            output_variable = args[0]
            option_dict = get_variable_dict(output_variable, result, options, reverses)
            option_dict["defined"].append(str(len(var_list_dict["items"])))
        else:
            # TODO: if not replace, unknown the actual length
            pass
        return

    def list_get(args):
        # sorted list we have no idea to strip them
        if len(args) < 2:
            raise capture_util.ParserError("List GET action analysis error!")
        # print(variable_name)
        # print(var_list_dict.get("is_replace", True))

        if var_list_dict.get("is_replace", False):
            output_variable = args[-1]
            elems = args[:-1]
            option_dict = get_variable_dict(output_variable, result, options, reverses, is_list=True)
            # print(option_dict)
            items = var_list_dict.get("items", list())
            for i in elems:
                idx = int(i)
                if idx >= len(items):
                    value = items[-1]
                elif idx < -len(items):
                    value = items[0]
                else:
                    value = idx
                item = items[value]
                option_dict["items"].append(item)
        else:
            pass
        return

    def list_find(args):
        # Can do nothing
        if len(args) != 2:
            raise capture_util.ParserError("List FIND action analysis error!")
        return

    def list_append(args):
        if len(args) == 0:
            return
        elems = args
        for elem in elems:
            var_dict = {
                "defined": [],
                "undefined": []
            }
            temp = ""
            values = capture_util.split_line(elem)
            for (i, word) in enumerate(values):
                temp = temp + " " + word if temp else word
                if i != len(values) - 1 and word in filename_flags and values[i + 1][0] != '-':
                    continue

                value_with_quote_match = re.match(r"\"([^\\\"]*)\"", temp, flags=re.DOTALL)
                if value_with_quote_match:
                    value = value_with_quote_match.group(1)
                else:
                    value = temp

                # TODO: Here we just replace a simple single value var, ignore list var replaces.
                slices = capture_util.undefined_split(value, var_dict)
                transfer_word = "".join(slices)

                if check_undefined(slices, with_ac_var=False):
                    var_dict["undefined"].append(transfer_word)
                else:
                    var_dict["defined"].append(transfer_word)
                temp = ""
            var_list_dict["items"].append(var_dict)
        return

    def list_insert(args):
        if len(args) < 2:
            raise capture_util.ParserError("List INSERT action analysis error!")
        if var_list_dict.get("is_replace", False):
            idx = args[0]
            elems = args[1:]
            items = var_list_dict.get("items", list())
            new_items =  items[:idx]
            for elem in elems:
                var_dict = {
                    "defined": [],
                    "undefined": []
                }
                temp = ""
                values = capture_util.split_line(elem)
                for (i, word) in enumerate(values):
                    temp = temp + " " + word if temp else word
                    if i != len(values) - 1 and word in filename_flags and values[i + 1][0] != '-':
                        continue

                    value_with_quote_match = re.match(r"\"([^\\\"])\"", temp, flags=re.DOTALL)
                    if value_with_quote_match:
                        value = value_with_quote_match.group(1)
                    else:
                        value = word

                    # TODO: Here we just replace a simple single value var, ignore list var replaces.
                    slices = capture_util.undefined_split(value, var_dict)
                    transfer_word = "".join(slices)

                    if check_undefined(slices, with_ac_var=False):
                        var_dict["undefined"].append(transfer_word)
                    else:
                        var_dict["defined"].append(transfer_word)
                    temp = ""
                new_items.append(var_dict)
            new_items.extend(items[idx:])
            var_list_dict["items"] = new_items
        else:
            pass
        return

    def list_remove_item(args):
        # Do nothing
        if len(args) < 1:
            raise capture_util.ParserError("List REMOVE_ITEM action analysis error!")
        pass

    def list_remove_at(args):
        if len(args) < 1:
            raise capture_util.ParserError("List REMOVE_AT action analysis error!")
        pass

    def list_remove_duplicates(args):
        if len(args) != 0:
            raise capture_util.ParserError("List DUPLICATES action analysis error!")
        pass

    def list_reverse(args):
        if len(args) != 0:
            raise capture_util.ParserError("List REVERSE action analysis error!")
        if var_list_dict.get("is_replace", False):
            items = var_list_dict.get("items", list())
            var_list_dict["items"] = items.reverse()
        else:
            pass
        return

    def list_sort(args):
        if len(args) != 0:
            raise capture_util.ParserError("List SORT action analysis error!")
        pass

    def list_error(args):
        raise capture_util.ParserError("List command action not found!")

    action_dict = {
        "LENGTH": list_length,
        "GET": list_get,
        "FIND": list_find,
        "APPEND": list_append,
        "INSERT": list_insert,
        "REMOVE_ITEM": list_remove_item,
        "REMOVE_AT": list_remove_at,
        "REMOVE_DUPLICATES": list_remove_duplicates,
        "REVERSE": list_reverse,
        "SORT": list_sort,
    }

    action_func = action_dict.get(action, list_error)
    action_func(words[2:])
    return


# 2. option control
level_options = []


def if_analyzer(match_args_line, options, reverses):
    options.append(match_args_line)
    level_options.append(match_args_line)
    reverses.append(False)
    return


def elseif_analyzer(match_args_line, options, reverses):
    if len(options) == 0:
        raise capture_util.ParserError("CMake analysis error when analysis elseif(%s)"
                                       % match_args_line)
    options.pop()
    reverses[-1] = False
    options.append(match_args_line)
    level_options.append(match_args_line)
    return


def else_analyzer(match_args_line, options, reverses):
    if len(options) == 0:
        raise capture_util.ParserError("CMake analysis error when analysis else()")
    if len(level_options) > 1:
        option_str = "OR".join(map("({})".format, level_options))
        option_str = "NOT ({})".format(option_str)
        options.pop()
        options.append(option_str)
        reverses[-1] = False
    else:
        reverses[-1] = not reverses[-1]
    return


def endif_analyzer(match_args_line, options, reverses):
    if len(options) == 0:
        raise capture_util.ParserError("CMake analysis error when analysis endif()")
    options.pop()
    reverses.pop()
    return


# 3. include
def include_directories_analyzer(match_args_line, result, options, reverses):
    pass


# 4. macros
def add_definitions_analyzer(match_args_line, result, options, reverses):
    # 采用add_definitions来添加宏定义的方式，会继承到下一级的cmakelists.txt文件中
    # TODO: 宏定义的写法有两种 -D...  /D...
    var_dict = result.get("variables", dict())
    definitions_dict = result.get("definitions", dict())
    option_definitions_dict = get_option_level(definitions_dict, options, reverses)
    words = capture_util.split_line(match_args_line)
    for (i, word) in enumerate(words):
        value = word.replace("/D", "-D")
        slices = capture_util.undefined_split(value, var_dict)
        transfer_word = "".join(slices)
        if check_undefined(slices, with_ac_var=False):
            option_definitions_dict["defined"].append(transfer_word)
        else:
            option_definitions_dict["undefined"].append(transfer_word)
    return


# 5. flags
def add_compile_options_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variables", dict())
    flags_dict = result.get("flags", dict())
    definitions_dict = result.get("definitions", dict())
    option_flags = get_option_level(flags_dict, options, reverses)
    words = capture_util.split_line(match_args_line)
    temp = ""
    for (i, word) in enumerate(words):
        temp = temp + " " + word if temp else word
        if i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-':
            continue

        # Move Macros flags from flags to definitions.
        # TODO: we can move -I flags to includes
        if re.match(r"-D", temp):
            option_dict = get_option_level(definitions_dict, options, reverses)
        else:
            option_dict = option_flags

        slices = capture_util.undefined_split(word, var_dict)
        transfer_word = "".join(slices)
        if check_undefined(slices, with_ac_var=False):
            option_dict["defined"].append(transfer_word)
        else:
            option_dict["undefined"].append(transfer_word)
        temp = ""
    return


# other config command
def set_target_properties_analyzer(match_args_line, result, options, reverses):
    target_dict = result.get("target", dict())
    var_dict = result.get("variables", dict())
    words = capture_util.split_line(match_args_line)
    idx = 0
    targets = []
    try:
        while words[idx] != "PROPERTIES":
            # TODO: 还存在一个严重的问题，如果target的名称也是一个变量，那么做起来就很麻烦了。。。,可以考虑直接使用变量来存储key了。。。
            if words[idx] not in target_dict:
                # If not found target or target is not append by us, we will not add it to targets.
                logger.warning("Not found target: %s in output_target." % words[idx])
            else:
                targets.append(words[idx])
            idx += 1

        idx += 1
        values = []
        target_property = ""
        for word in words[idx:]:
            if word not in target_properties_set:
                values.append(word)
            else:
                if len(target_property) == 0:
                    target_property = word
                    if len(values) != 0:
                        raise capture_util.ParserError("set_target_properties properties fields error!")
                else:
                    value = " ".join(values)
                    for target_name in targets:
                        target = target_dict.get(target_name, dict())
                        option_target = get_target_dict(target_property, target, options, reverses)
                        slices = capture_util.undefined_split(value, var_dict)
                        transfer_word = "".join(slices)
                        if check_undefined(slices, with_ac_var=False):
                            if check_undefined_self(slices, target_property):
                                if len(slices) == 1:
                                    option_target["is_replace"] = False
                                continue
                            option_target["undefined"].append(transfer_word)
                        else:
                            option_target["defined"].append(transfer_word)
                    values.clear()
        value = " ".join(values)
        for target_name in targets:
            target = target_dict.get(target_name, dict())
            option_target = get_target_dict(target_property, target, options, reverses)
            slices = capture_util.undefined_split(value, var_dict)
            transfer_word = "".join(slices)
            if check_undefined(slices, with_ac_var=False):
                if check_undefined_self(slices, target_property):
                    if len(slices) == 1:
                        option_target["is_replace"] = False
                    continue
                option_target["undefined"].append(transfer_word)
            else:
                option_target["defined"].append(transfer_word)
    except IndexError:
        raise capture_util.ParserError("set_target_properties arguments analysis error!")
    return


def transform_makefile_inc_analyzer(match_args_line, result, options, reverses):
    pass


# add target
def add_executable_analyzer(match_args_line, result, options, reverses):
    pass


def add_library(match_args_line, result, options, reverses):
    pass


if __name__ == "__main__":
    if len(sys.argv) == 2:
        filename = sys.argv[1]
    else:
        sys.stderr.write("Error, without filename.\n")
        sys.exit(-1)

    result = {
        "variables": dict(),
        "list_variables": dict(),
        "target": {
            "libcurl": dict()
        },

        # 全局的definitions，可以继承到下一级, 主要是通过add_defnitions() 添加的
        "definitions": {
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
        }
    }
    options = []
    reverses = []

    with open(filename, "r") as fin:
        data = fin.read()
        data = data.lstrip(" \t\n")
        lines = []
        set_regex = re.compile(r"[Ss][Ee][Tt]\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
        list_regex = re.compile(r"[Ll][Ii][Ss][Tt]\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
        if_regex = re.compile(r"[Ii][Ff]\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
        elseif_regex = re.compile(r"[Ee][Ll][Ss][Ee][Ii][Ff]\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
        else_regex = re.compile(r"[Ee][Ll][Ss][Ee]\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
        endif_regex = re.compile(r"[Ee][Nn][Dd][Ii][Ff]\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
        set_target_properties_regex = re.compile(r"set_target_properties\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)

        while len(data) != 0:
            set_match = set_regex.match(data)
            list_match = list_regex.match(data)
            if_match = if_regex.match(data)
            elseif_match = elseif_regex.match(data)
            else_match = else_regex.match(data)
            endif_match = endif_regex.match(data)
            set_target_properties_match = set_target_properties_regex.match(data)
            if set_match:
                line = set_match.group(1)
                set_analyzer(line, result, options=options, reverses=reverses)
                data = set_match.group(2)
            elif list_match:
                line = list_match.group(1)
                list_analyzer(line, result, options=options, reverses=reverses)
                data = list_match.group(2)
            elif if_match:
                line = if_match.group(1)
                if_analyzer(line, options=options, reverses=reverses)
                data = if_match.group(2)
            elif elseif_match:
                line = elseif_match.group(1)
                elseif_analyzer(line, options=options, reverses=reverses)
                data = elseif_match.group(2)
            elif else_match:
                line = else_match.group(1)
                else_analyzer(line, options=options, reverses=reverses)
                data = else_match.group(2)
            elif endif_match:
                line = endif_match.group(1)
                endif_analyzer(line, options=options, reverses=reverses)
                data = endif_match.group(2)
            elif set_target_properties_match:
                line = set_target_properties_match.group(1)
                set_target_properties_analyzer(line, result, options, reverses)
                data = set_target_properties_match.group(2)
            else:
                logger.warning("file analyze fail with an unknown line '%s' in %s." %
                               (data.split("\n")[0], fin.name))
                index = data.find("\n")
                data = data[index:]
            data = data.lstrip(" \t\n")

    import json
    with open("./data_result.out", "w") as fout:
        json.dump(result, fout, indent=4)

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
