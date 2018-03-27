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
    undefined_pattern = r"\$[a-zA-Z_][a-zA-Z0-9_]*|\$\([a-zA-Z_][a-zA-Z0-9_]*\)"
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


# 2. include
def include_directories_analyzer(match_args_line, result, option, reverse):
    pass


# other config command
def set_target_properties_analyzer(match_args_line, result, option, reverse):
    pass


def transform_makefile_inc_analyzer(match_args_line, result, options, reverses):
    pass

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent


if __name__ == "__main__":
    if len(sys.argv) == 2:
        filename = sys.argv[1]
    else:
        sys.stderr.write("Error, without filename.\n")
        sys.exit(-1)

    result = {
        "variables": dict(),
        "list_variables": dict()
    }

    with open(filename, "r") as fin:
        data = fin.read()
        data = data.lstrip(" \t\n")
        lines = []
        set_regex = re.compile(r"[Ss][Ee][Tt]\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
        list_regex = re.compile(r"[Ll][Ii][Ss][Tt]\(\s*(.*?)\s*\)(.*)", flags=re.DOTALL)
        while len(data) != 0:
            set_match = set_regex.match(data)
            list_match = list_regex.match(data)
            if set_match:
                line = set_match.group(1)
                set_analyzer(line, result, options=[], reverses=[])
                data = set_match.group(2)
            elif list_match:
                line = list_match.group(1)
                list_analyzer(line, result, options=[], reverses=[])
                data = list_match.group(2)
            else:
                logger.warning("file analyze fail with an unknown line '%s' in %s." %
                               (data.split("\n")[0], fin.name))
                index = data.find("\n")
                data = data[index:]
            data = data.lstrip(" \t\n")

    import json
    with open("./data_result.out", "w") as fout:
        json.dump(result, fout, indent=4)
