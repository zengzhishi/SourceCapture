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
import os
import re
import sys
import logging

# import capture_util
# import parse_autotools
# if __name__ == "__main__":
#     import capture_util
#     sys.path.append("../conf")
#     import parse_logger
#     parse_logger.addFileHandler("./capture.log", "capture")
# else:
import capture.utils.capture_util as capture_util
import capture.utils.parse_autotools as parse_autotools

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
    for i, slice in enumerate(slices):
        if check_one_undefined_slice_self(slice, self_var):
            return True, i
    return False, -1


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
dir_name = os.path.dirname(__file__)
with open(os.path.join(dir_name, "cmake_target_properties.txt"), "r") as fin:
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


def check_variable(word):
    dollar_var_pattern = r"\$[\({]([a-zA-Z_][a-zA-Z0-9_]*)[\)}"
    with_var_line_regex = re.compile(dollar_var_pattern)
    with_var_line_match = with_var_line_regex.match(word)



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


def get_defined_value(option_dict):
    if len(option_dict.get("option", dict())) == 0 and \
            len(option_dict.get("undefined", dict())) == 0:
        defineds = option_dict.get("defined", list())
        value = " ".join(defineds)
        return value
    return None


# 1. Argument config command
def set_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variables", dict())
    list_var_dict = result.get("list_variables", dict())

    # 1. variable
    # TODO: consider whether we need a env_variable dict
    variable_regex = re.compile("\s*(" + var_pattern + ")\s+(.*)|\s*(" + var_pattern + ")", flags=re.DOTALL)
    variable_match = variable_regex.match(match_args_line)
    env_regex = re.compile("\s*ENV{(" + var_pattern + ")}\s+(.*)|\s*ENV{(" + var_pattern + ")}", flags=re.DOTALL)
    env_match = env_regex.match(match_args_line)

    # SET variable is a ${} type, is difficult to analysis.
    if not variable_match and not env_match:
        logger.warning("Set pattern error in set({}). var_name is not a defined value.".format(match_args_line))
        return

    if variable_match:
        variable_name = variable_match.group(1) if variable_match.group(1) is not None else variable_match.group(3)
        match_line = variable_match.group(2) if variable_match.group(1) is not None else ""
    else:
        variable_name = env_match.group(1) if env_match.group(1) is not None else env_match.group(3)
        match_line = env_match.group(2) if env_match.group(1) is not None else ""

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

    elif len(words) == 1 or len(words) > 1 and re.match(r"CACHE|PARENT_SCOPE", words[1]):
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

            value_with_quote_match = re.match(r"\"([^\\\"]*)\"", temp, flags=re.DOTALL)
            if value_with_quote_match:
                value = value_with_quote_match.group(1)
            else:
                value = word
            slices = capture_util.undefined_split(value, var_dict)

            # TODO: 暂时无法表达 string 拼接操作
            self_status, idx = check_undefined_self(slices, variable_name)
            if self_status:
                if len(slices) == 1:
                    option_dict["is_replace"] = False
                    temp = ""
                    continue
                elif len(var_dict.get("option", dict())) == 0 and \
                        len(var_dict.get("undefined", list())) == 0:
                    value = " ".join(var_dict.get("defined", list()))
                    slices[idx] = value
                else:
                    temp = ""
                    continue
            transfer_word = "".join(slices)
            if check_undefined(slices, with_ac_var=False):
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


def project_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variables", dict())
    words = capture_util.split_line(match_args_line)
    if len(words) == 0:
        raise capture_util.ParserError("Unable to analyze project command args_line: ' %s '" % match_args_line)

    # TODO: May be we can get other project config here
    project_name = words[0]
    value_dict = var_dict.get("CMAKE_SOURCE_DIR", dict())
    var_dict["{}_SOURCE_DIR".format(project_name.upper())] = value_dict
    var_dict["PROJECT_SOURCE_DIR"] = value_dict
    value_dict = var_dict.get("CMAKE_BINARY_DIR", dict())
    var_dict["{}_BINARY_DIR".format(project_name.upper())] = value_dict
    var_dict["PROJECT_BINARY_DIR"] = value_dict
    return


def add_subdirectory_analyzer(match_args_line, result, options, reverses):
    # Don't care about options status, just append all directories.
    var_dict = result.get("variables", dict())
    subdirectory_list = result.get("subdirectories", list())
    words = capture_util.split_line(match_args_line)
    if len(words) == 0:
        raise capture_util.ParserError("add_subdirectory command analyze fail. args_line: '%s'" % match_args_line)

    subdirectory_name = words[0]
    value_dict = var_dict.get("CMAKE_SOURCE_DIR", dict())
    value = get_defined_value(value_dict)
    sub_path = os.path.join(value, subdirectory_name)
    if os.path.exists(sub_path):
        subdirectory_list.append(sub_path)
    return


# 2. option control
level_options = []


def if_analyzer(match_args_line, result, options, reverses):
    options.append(match_args_line)
    level_options.append(match_args_line)
    reverses.append(False)
    return


def elseif_analyzer(match_args_line, result, options, reverses):
    if len(options) == 0:
        raise capture_util.ParserError("CMake analysis error when analysis elseif(%s)"
                                       % match_args_line)
    options.pop()
    reverses[-1] = False
    options.append(match_args_line)
    level_options.append(match_args_line)
    return


def else_analyzer(match_args_line, result, options, reverses):
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


def endif_analyzer(match_args_line, result, options, reverses):
    if len(options) == 0:
        raise capture_util.ParserError("CMake analysis error when analysis endif()")
    level_options.clear()
    options.pop()
    reverses.pop()
    return


# 3. include
def include_directories_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variables", dict())
    includes_dict = result.get("includes", dict())
    words = capture_util.split_line(match_args_line)
    for (i, word) in enumerate(words):
        if i == 0 or i == 1:
            if re.match("AFTER|BEFORE|SYSTEM", word):
                continue

        slices = capture_util.undefined_split(word, var_dict)
        transfer_word = "".join(slices)
        if check_undefined(slices, with_ac_var=False):
            includes_dict["undefined"].append(transfer_word)
        else:
            includes_dict["defined"].append(transfer_word)
    return


# For target include, but just directly move them to global value.
def target_include_directories_analyzer(match_args_line, result, options, reverses):
    includes_dict = result.get("includes", dict())
    var_dict = result.get("variable", dict())
    option_includes_dict = get_option_level(includes_dict, options, reverses)
    words = capture_util.split_line(match_args_line)
    allow_add_item = False
    for (i, word) in enumerate(words):
        if re.match(r"INTERFACE|PUBLIC|PRIVATE", word):
            allow_add_item = True
        if allow_add_item and not re.match(r"INTERFACE|PUBLIC|PRIVATE", word):
            slices = capture_util.undefined_split(word, var_dict)
            transfer_word = "".join(slices)
            if check_undefined(slices, with_ac_var=False):
                option_includes_dict["undefined"].append(transfer_word)
            elif re.match("\$<.*?>", word):
                # generator command may be difficult to analyze.
                pass
            else:
                option_includes_dict["defined"].append(transfer_word)
    return


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
            option_definitions_dict["undefined"].append(transfer_word)
        else:
            option_definitions_dict["defined"].append(transfer_word)
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


# 6. option for generating config.h
def option_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variables", dict())
    config_dict = result.get("config_option", dict())
    words = capture_util.split_line(match_args_line)
    if len(words) > 0:
        name = words[0]
        docstring = ""
        initial_value = "OFF"
    else:
        raise capture_util.ParserError("option analysis fail. 'option(%s)' " % match_args_line)

    # docstring presently will not be used.
    if len(words) == 2:
        if re.match(r"ON|OFF", words[1]):
            initial_value = words[1]
        else:
            docstring = words[1]

    if len(words) == 3:
        initial_value = words[2]

    if name not in config_dict:
        config_dict[name] = {
            "defined": [],
            "undefined": [],
            "option": {},
            "is_replace": True
        }
    present_var_config_dict = config_dict.get(name)
    option_config_dict = get_option_level(present_var_config_dict, options, reverses)
    value = capture_util.strip_quotes(initial_value)
    slices = capture_util.undefined_split(value, var_dict)
    transfer_word = "".join(slices)
    if check_undefined(slices, with_ac_var=False):
        option_config_dict["undefined"].append(transfer_word)
    else:
        option_config_dict["defined"].append(transfer_word)
    return


def configure_file_analyzer(match_args_line, result, options, reverses):
    # TODO: 只提取最终生成 .h文件就可以, 其他的太麻烦了
    pass


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
                match = re.match("\${(.*?)}", words[idx])
                value = words[idx]
                if match:
                    name = match.group(1)
                    value_dict = var_dict.get(name, dict())
                    tmp_value = get_defined_value(value_dict)
                    if tmp_value is not None:
                        value = tmp_value
                targets.append(value)
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
    var_dict = result.get("variables", dict())
    words = capture_util.split_line(match_args_line)
    if len(words) != 2:
        logger.warning("Can't analyze transform_makefile_inc(%s)" % match_args_line)
        return
    src = capture_util.strip_quotes(words[0])
    des = capture_util.strip_quotes(words[1])
    src_slices = capture_util.undefined_split(src, var_dict)
    des_slices = capture_util.undefined_split(des,var_dict)
    # If transform_makefile_inc value can't be strip out, we will not build it.
    if check_undefined(src_slices) or check_undefined(des_slices):
        return

    for value in (src, des):
        value_with_quote_match = re.match(r"\"([^\\\"]*)\"", value, flags=re.DOTALL)
        if value_with_quote_match:
            if value == src:
                src = value_with_quote_match.group(1)
            else:
                # Here will don't need to generate output file .cmake, just directly loading makefile.inc data
                # to var_dict
                des = value_with_quote_match.group(1)

    if not os.path.isabs(src):
        value_dict = var_dict.get("CMAKE_CURRENT_SOURCE_DIR", dict())
        value = get_defined_value(value_dict)
        if value is not None:
            src = os.path.join(value, src)

    src_base_name = os.path.basename(src)
    src_base_name_pattern = get_command_name_pattern("makefile.inc", with_lparen=False)
    if re.match(src_base_name_pattern, src_base_name):
        value_dict = var_dict.get("CMAKE_SOURCE_DIR", dict())
        value = get_defined_value(value_dict)
        value_dict = var_dict.get("CMAKE_BINARY_DIR", dict())
        build_value = get_defined_value(value_dict)
        if value is not None and build_value is not None and os.path.exists(src):
            build_path = os.path.dirname(build_value)
            auto_tools_parser = parse_autotools.AutoToolsParser(value, build_path)
            auto_tools_parser.loading_include(var_dict, src, options, reverses)


# add target
# TODO: target 解析存在问题， 1.对于没有显示写入的目标（变量），缺少获取值
# 2. 没有解析source部分, 应该可以做一个简单的source解析
def add_library_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variables", dict())
    target_dict = result.get("target", dict())
    words = capture_util.split_line(match_args_line)
    if words == 0:
        logger.warning("Add Lib target fail.")
        return
    target_name = words[0]
    target_list = [target_name]
    words = words[1:]
    variable_regex = re.compile("\s*(" + var_pattern + ")\s+(.*)", flags=re.DOTALL)
    variable_match = variable_regex.match(match_args_line)
    match = re.match("\${(.*?)}", target_name)
    if match:
        # lib name may be use ${}
        name = match.group(1)

        value_dict = var_dict.get(name, dict())
        value = get_defined_value(value_dict)
        if value is not None:
            target_list.append(value)

    elif not variable_match:
        logger.warning("Lib target name strip fail.")
        return

    library_type = None
    if len(words) > 1 and re.match("STATIC|SHARED|MODULE", words[0]):
        library_type = words[0] + "LIBRARY"
        words = words[1:]

    # sources 暂时不处理
    for target_name in target_list:
        target_dict[target_name] = dict()
        if library_type is not None:
            target_dict[target_name]["TYPE"] = library_type
    return


def add_executable_analyzer(match_args_line, result, options, reverses):
    var_dict = result.get("variables", dict())
    target_dict = result.get("target", dict())
    words = capture_util.split_line(match_args_line)
    if words == 0:
        logger.warning("Add Executable target fail.")
        return
    target_name = words[0]
    target_list = [target_name]
    words = words[1:]
    variable_regex = re.compile("\s*(" + var_pattern + ")\s+(.*)", flags=re.DOTALL)
    variable_match = variable_regex.match(match_args_line)
    match = re.match("\${(.*?)}", target_name)
    if match:
        name = match.group(1)

        value_dict = var_dict.get(name, dict())
        value = get_defined_value(value_dict)
        if value is not None:
            target_list.append(value)

    elif not variable_match:
        logger.warning("Executable target name strip fail.")
        return

    # sources 暂时不处理
    for target_name in target_list:
        target_dict[target_name] = dict()
    return


# other
def set_property_analyzer(match_args_line, result, options, reverses):
    scope_target_dict = result.get("scope_target", dict())
    var_dict = result.get("variables", dict())

    words = capture_util.split_line(match_args_line)
    try:
        scopename = words[0]
        idx = 1
        target_list = []
        to_delete_idx = []
        # TODO: 这里没有区分list 和 string来存储
        is_list = False
        while words[idx] != "PROPERTY":
            if words[idx] == "APPEND_STRING":
                to_delete_idx.append(idx)
            if words[idx] == "APPEND":
                is_list = True
                to_delete_idx.append(idx)
            else:
                target_list.append(words[idx])
            idx += 1
        to_delete_idx.sort(reverse=True)

        if scopename == "TARGET":
            words[idx] = "PROPERTIES"
            [words.pop(i) for i in to_delete_idx]
            words.pop(0)
            target_match_args_line = " ".join(words)
            return set_target_properties_analyzer(target_match_args_line, result, options, reverses)
        else:
            # Here will storage all property value.
            idx += 1
            property_name = words[idx]
            option_dict = get_target_dict(property_name, scope_target_dict, options, reverses)
            for word in words[idx + 1:]:
                value = capture_util.strip_quotes(word)
                slices = capture_util.undefined_split(value, var_dict)
                transfer_word = "".join(slices)
                if check_undefined(slices, with_ac_var=False):
                    option_dict["undefined"].append(transfer_word)
                else:
                    option_dict["defined"].append(transfer_word)
    except IndexError:
        raise capture_util.ParserError("set_properties arguments analysis error!")
    return


def not_found_analyzer(match_args_line, result, options, reverses):
    logger.warning("Not found analyzer for such command")
    return


def get_next_rparen(s):
    if len(s) == 0:
        return None
    idx = s.find(")")
    if idx != -1:
        return s[:idx]
    return ""


def get_cmake_command(s, cmake_path, result):
    """A generator to analysis cmake commands from CMakeLists.txt"""
    # TODO: May be we need to statistic the present checking line and lexer position, in order to print logger.
    var_dict = result.get("variables", dict())
    present_str = s
    if len(present_str) == 0:
        return
    comment_regex = re.compile(r"\s*#(.*?)\n(.*)", flags=re.DOTALL)
    command_regex = re.compile(r"\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
    include_regex = re.compile(r"\s*include\s*\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
    present_str = present_str.lstrip(" \t\n")
    while len(present_str) != 0:
        comment_match = comment_regex.match(present_str)
        command_match = command_regex.match(present_str)
        include_match = include_regex.match(present_str)
        if comment_match:
            comment_line = comment_match.group(1)
            present_str = comment_match.group(2)
        elif include_match:
            include_args_line = include_match.group(1)
            present_str = include_match.group(2)
            words = capture_util.split_line(include_args_line)
            dest = words[0]
            dest = capture_util.strip_quotes(dest)
            slices = dest.split(".")
            if len(slices) > 1:
                # Use file path
                if slices[-1] == "cmake":
                    slices = capture_util.undefined_split(dest)
                    values = []
                    for slice in slices:
                        variable_match = re.match(r"(.*)\$[\({]([a-zA-Z_][a-zA-Z0-9_]*)[\)}](.*)", slice)
                        if variable_match:
                            name = variable_match.group(2)
                            value = get_defined_value(var_dict.get(name, dict()))
                            if value is None:
                                values = None
                                break
                            values.append(value)
                        else:
                            values.append(slice)
                    if values is not None:
                        transfer_dest = "".join(values)
                        file_path = os.path.join(cmake_path, transfer_dest)
                        if os.path.exists(file_path):
                            with open(file_path, "r") as fin:
                                data = fin.read()
                                data += present_str
                                present_str = data
                else:
                    logger.warning("Unknown cmake module file to include")
            else:
                # Use module name
                if "CMAKE_MODULE_PATH" not in var_dict:
                    logger.warning("Couldn't found cmake module file in module path.")
                    continue
                cmake_module_path = var_dict.get("CMAKE_MODULE_PATH", dict())
                arg_value = get_defined_value(cmake_module_path)
                if arg_value is None:
                    continue
                module_paths_str = " ".join(cmake_module_path.get("defined", list()))
                module_paths = module_paths_str.split(";")
                module_paths = filter(lambda path: len(path) != 0, module_paths)
                data = ""
                for module_path in module_paths:
                    if not os.path.isabs(module_path):
                        file_path = os.path.join(cmake_path, module_path, dest + ".cmake")
                    else:
                        file_path = os.path.join(module_path, dest + ".cmake")
                    if os.path.exists(file_path):
                        with open(file_path, "r") as fin:
                            data = fin.read()
                        break
                if len(data) == 0:
                    logger.warning("Not found cmake module.")
                data += present_str
                present_str = data
        elif command_match:
            command_name = command_match.group(1)
            match_args_line = command_match.group(2)
            present_str = command_match.group(3)
            double_quote_count = len(re.findall(r'"', match_args_line))
            double_quote_exclude_count = len(re.findall(r"\\\"", line))
            lparen_count = len(re.findall("\(", match_args_line))
            rparen_count = len(re.findall("\)", match_args_line))
            while (double_quote_count - double_quote_exclude_count) % 2 != 0 or \
                lparen_count - rparen_count > 0:
                next_str = get_next_rparen(present_str)
                if next_str is None and next == "":
                    raise capture_util.ParserError("Command analysis fail!")
                match_args_line += ")" + next_str
                double_quote_count = len(re.findall(r'"', match_args_line))
                double_quote_exclude_count = len(re.findall(r"\\\"", match_args_line))
                lparen_count = len(re.findall("\(", match_args_line))
                rparen_count = len(re.findall("\)", match_args_line))
                present_str = present_str[len(next_str) + 1:]
            yield command_name, match_args_line
        else:
            logger.warning("Command_analysis error happend in line: '%s'" %
                           present_str.split("\n")[0])
            i = present_str.find("\n")
            present_str = present_str[i:]

        present_str = present_str.lstrip(" \t\n")


def get_command_name_pattern(name, with_lparen=True):
    pattern_name = r""
    for i in name:
        if re.match("[a-zA-Z]", i):
            pattern_name += r"[{}{}]".format(i.lower(), i.upper())
        else:
            pattern_name += i
    if with_lparen:
        pattern_name += r"\("
    return pattern_name


def get_command_analyzer(name):
    # TODO: Need to add default function when no analyzer in this module
    current_module = sys.modules[__name__]
    analyzer_funcname = "{}_analyzer".format(name.lower())
    return getattr(current_module, analyzer_funcname)


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
    options = []
    reverses = []

    with open(filename, "r") as fin:
        data = fin.read()
        data = data.lstrip(" \t\n")
        commands = [
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
        commands.sort(key=len, reverse=True)
        command_name_patterns = map(lambda command: get_command_name_pattern(command), commands)
        command_pattern = "|".join(command_name_patterns)
        command_regex = re.compile(command_pattern)
        # TODO: Need to add some process for self-defined function analyze.
        cmake_path = os.path.dirname(filename)
        for command_name, args_line in get_cmake_command(data, cmake_path, result):
            print(command_name)
            if not command_regex.match(command_name + "("):
                # Command we don't care will be passed.
                continue
            analyzer = get_command_analyzer(command_name)
            analyzer(args_line, result, options, reverses)

    import json
    with open("./data_result.out", "w") as fout:
        json.dump(result, fout, indent=4)

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
