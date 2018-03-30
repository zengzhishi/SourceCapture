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
import queue
import logging
import json
import random

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

# Cache for var_dict option analysis result.
temp_var_options = {}


def merge_option(src_option, dest_option, deepcopy=True):
    """Util function to copy data from src_option to dest_option."""
    if deepcopy:
        result_option = {
            "defined": copy.deepcopy(dest_option.get("defined", list())),
            "undefined": copy.deepcopy(dest_option.get("undefined", list()))
        }
    else:
        result_option = {
            "defined": dest_option.get("defined", list()),
            "undefined": dest_option.get("undefined", list())
        }

    for defined in src_option.get("defined", list()):
        if defined not in result_option.get("defined", list()):
            result_option["defined"].append(defined)

    for undefined in src_option.get("undefined", list()):
        if undefined not in result_option.get("undefined", list()):
            result_option["undefined"].append(undefined)

    result_option["option"] = dest_option.get("option", dict())
    return result_option


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


def get_variable_value_without_option(var_dict, result, iter_all_level=False):
    """
    Get all defined value form var_dict.
    :param var_dict:                        variable dict to be strip value.
    :param result:                          result dict to storage analysis info.
    :param iter_all_level:
    :return:
    """
    variable_dict = result.get("variables", dict())
    list_variable_dict = result.get("list_variables", dict())
    q = queue.Queue()
    q.put(var_dict)
    values = []
    is_complete = False
    while not is_complete:
        try:
            present_option_dict = q.get(block=False)
        except queue.Empty:
            is_complete = True
            present_option_dict = dict()
        defineds = present_option_dict.get("defined", list())
        undefineds = present_option_dict.get("undefined", list())
        options = present_option_dict.get("option", dict())
        [q.put(option) for option in options.values()]
        for undefined in undefineds:
            slices = capture_util.undefined_split(undefined, variable_dict)
            has_var = False
            for slice in slices:
                match = re.match("\${(.*?)}", slice)
                if match:
                    has_var = True
            if has_var:
                values.append("".join(slices))
        values.extend(defineds)

    return values


def option_builder(var_dict):
    """
    Generator to recall option dict, which will search all level option.
    :param var_dict:                variable store dict.
    :return:
    """
    dict_id = id(var_dict)
    if dict_id in temp_var_options:
        logger.debug("### Found %s" % dict_id)
        result_missions_list = temp_var_options.get(dict_id, [""])
        for missions_line in result_missions_list:
            yield json.loads(missions_line)
        return
    logger.debug("### Not Found %s" % dict_id)

    q = queue.Queue()

    # Ignore default N options
    options = var_dict.get("option", dict())
    options_key = options.keys()
    default_prefix = "default_"
    i = 1
    defaultN = default_prefix + str(i)
    if defaultN in options:
        status = True
        while status:
            options_key.pop(defaultN)
            i += 1
            defaultN = default_prefix + str(i)
            status = (defaultN in options)

    new_var_dict = merge_option(var_dict, dict())
    for key in options_key:
        new_var_dict["option"][key] = options.get(key, dict())
    missions = [(new_var_dict, 0)]
    logger.debug("$# start missions: %s" % missions)
    q.put(missions)

    # Start iterating all level option
    complete = False
    result_missions_set = set()
    while not complete:
        try:
            missions = q.get(block=False)
        except queue.Empty:
            complete = True
            continue

        option_check_flag = True
        for i, mission in enumerate(missions):
            var_dict = mission[0]
            level = mission[1]
            is_bool = True if True in var_dict else False
            is_bool_str = True if "true" in var_dict else False
            if "option" not in var_dict and (is_bool or is_bool_str):
                # option level
                true_missions = missions[:i]
                true_opt = var_dict.get(True if is_bool else "true", dict())
                true_missions.append((true_opt, level + 1))
                true_missions.extend(missions[i + 1:])

                false_missions = missions[:i]
                false_opt = var_dict.get(False if is_bool else "false", dict())
                false_missions.append((false_opt, level + 1))
                false_missions.extend(missions[i + 1:])

                q.put(true_missions)
                q.put(false_missions)
                option_check_flag = False
                break

            if "option" in var_dict and len(var_dict.get("option", dict())) != 0:
                options = var_dict.get("option", dict())
                # filter rule 1: More than level 3, we will stop checking.
                if level > 1:
                    var_dict["option"] = dict()

                # filter rule 2: More than 10 will use default value. We will use false value.
                use_top_options = False
                if len(options) > 10:
                    use_top_options = True

                # need to contain itself, but release option field
                start_missions = missions[:i]
                var_dict["option"] = {}
                start_missions.append((var_dict, level))
                for option in options:
                    option_dict = options[option]
                    is_bool = True if True in option_dict else False
                    if use_top_options:
                        option_dict = option_dict[False if is_bool else "false"]
                        option_dict["option"] = dict()
                    else:
                        start_missions.append((option_dict, level))
                start_missions.extend(missions[i + 1:])
                q.put(start_missions)
                option_check_flag = False
                break
        # Checking return type
        if len(missions) != 0 and option_check_flag:
            result_missions_set.add(json.dumps(missions))

    result_missions_list = list(result_missions_set)
    result_missions_list.sort(key=lambda line: len(line))
    temp_var_options[dict_id] = result_missions_list
    for missions_line in result_missions_list:
        yield json.loads(missions_line)


def undefined_builder(var_dict, result):
    """
        When we calling undefined builder we have been complete top level option check.
        TODO: 将这个函数修改为同时适用于 ac 部分的 variable 构建
    """
    variable_dict = result.get("variables", dict())
    first_queue = queue.Queue()
    second_queue = queue.Queue()

    line = " ".join(var_dict.get("undefined", list()))
    slices = capture_util.undefined_split(line, variable_dict)
    first_queue.put(["",])

    dollar_var_pattern = r"\s*\$[\({]([a-zA-Z_][a-zA-Z0-9_]*)[\)}]"
    var_regex = re.compile(dollar_var_pattern)
    complete = False
    level = 0
    while not complete:
        q = first_queue if level % 2 == 0 else second_queue
        next_q = second_queue if level % 2 == 0 else first_queue
        try:
            missions = q.get(block=False)
        except queue.Empty:
            if level == len(slices) - 1:
                complete = True
            level += 1
            continue

        slice = slices[level]
        var_match = var_regex.match(slice)
        with_blank = True if re.match("\s+", slice) else False
        if not var_match:
            missions.append(slice)
            next_q.put(missions)
        else:
            # export_var_flag = True if var_match.group(2) is not None else False
            # var_name = var_match.group(2) if export_var_flag else var_match.group(1)
            var_name = var_match.group(1)

            if var_name in variable_dict:
                for defined_list in get_variable_value_with_option(var_name, result, variable_dict[var_name]):
                    value = " ".join(defined_list)
                    value = " " + value if with_blank else value
                    temp_missions = copy.deepcopy(missions)
                    temp_missions.append(value)
                    next_q.put(temp_missions)
            else:
                # Unknown variable.
                value = ""
                value = " " + value if with_blank else value
                missions.append(value)
                next_q.put(missions)

    result_queue = first_queue if level % 2 == 0 else second_queue
    while not result_queue.empty():
        try:
            result_slices = result_queue.get(block=False)
            yield "".join(result_slices)
        except queue.Empty:
            continue


def get_variable_value_with_option(variable, result, option_dict, var_place="variables"):
    """A generator to recall option value for var_dict."""
    if isinstance(var_place, list):
        variable_dict = result
        for i in var_place:
            variable_dict = variable_dict.get(i, dict())
    elif isinstance(var_place, str):
        variable_dict = result.get(var_place, dict())
    else:
        variable_dict = result

    logger.info("# Start check value: %s" % variable)
    if variable not in variable_dict:
        yield [""]
        return

    undefineds = option_dict.get("undefined", list())
    defineds = option_dict.get("defined", list())
    options = option_dict.get("option", dict())
    print(option_dict)

    if len(options) != 0:
        for final_var_tuple in option_builder(option_dict):
            final_var_dict = merge_option(option_dict, dict())
            for opt, level in final_var_tuple:
                final_var_dict = merge_option(opt, final_var_dict)
            logger.info("final_var_dict: %s" % final_var_dict)
            undefineds = final_var_dict.get("undefined", list())
            defineds = final_var_dict.get("defined", list())

            if len(undefineds) == 0:
                yield defineds
            else:
                # Local ${} variable has been checking in local variables.
                # Here we need to check preset_variables and ac_subst variables.
                for undefined_line in undefined_builder(final_var_dict, result):
                    copy_defineds = copy.deepcopy(defineds)
                    copy_defineds.append(undefined_line)
                    yield copy_defineds
    else:
        if len(undefineds) == 0:
            yield defineds
        else:
            for undefined_line in undefined_builder(option_dict, result):
                copy_defineds = copy.deepcopy(defineds)
                copy_defineds.append(undefined_line)
                yield copy_defineds


class CMakeParser(object):
    __sample_result = {
        "variables": dict(),
        "list_variables": dict(),
        "target": dict(),
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
        "config_option": dict(),
        # Although subdirectory can be appended when under options, we just loading all of them to analyze.
        "subdirectories": list(),
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
        "transform_makefile_inc",
        "project",
        "add_subdirectory",
    ]

    def __init__(self, project_path, output_path, build_path=None, c_compiler="cc", cxx_compiler="g++"):
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

        self.c_compiler = c_compiler
        self.cxx_compiler = cxx_compiler

    def _add_default_value(self, cmakelist_path, parent_info=None):
        """
            This function will add some default value for cmake analyzer, like
            CMAKE_SOURCE_PATH, CMAKE_BINARY_PATH, CMAKE_MODULE_PATH and etc.

            TODO: 1. add default CMAKE_MODULE_PATH,
                  2. add CMAKE compiler and linker variables.
        """
        cmake_current_path = os.path.dirname(cmakelist_path)
        cmake_binary_current_path = get_relative_build_path(cmake_current_path, self._project_path,
                                                            self._build_path)

        if parent_info is None:
            self._cmake_info[cmakelist_path] = copy.deepcopy(self.__sample_result)
            if not os.path.isabs(cmake_current_path):
                cmake_current_path = os.path.join(self._project_path, cmake_current_path)
            one_cmake_info = self._cmake_info.get(cmakelist_path, self.__sample_result)
            var_dict = one_cmake_info.get("variables", dict())

            add_defined_value(var_dict, "CMAKE_SOURCE_DIR", self._project_path, list(), list())
            add_defined_value(var_dict, "CMAKE_CURRENT_SOURCE_DIR", cmake_current_path, list(), list())
            add_defined_value(var_dict, "CMAKE_BINARY_DIR", self._build_path, list(), list())
            add_defined_value(var_dict, "CMAKE_CURRENT_BINARY_DIR", cmake_binary_current_path, list(), list())
            # add_defined_value(var_dict, "CMAKE_MODULE_PATH", )
        else:
            self._cmake_info[cmakelist_path] = copy.deepcopy(parent_info)
            one_cmake_info = self._cmake_info.get(cmakelist_path, self.__sample_result)
            var_dict = one_cmake_info.get("variables", dict())
            # free local target and subdirectories.
            one_cmake_info["target"] = dict()
            one_cmake_info["subdirectories"] = list()
            # option value should be shared.
            one_cmake_info["config_option"] = parent_info.get("config_option", dict())

            var_dict["CMAKE_CURRENT_SOURCE_DIR"]["defined"][0] = cmake_current_path
            var_dict["CMAKE_CURRENT_BINARY_DIR"]["defined"][0] = cmake_binary_current_path

        return

    def dump_cmake_info(self):
        import json
        with open(os.path.join(self._output_path, "cmake_info.json"), "w") as fout:
            json.dump(self._cmake_info, fout, indent=4)

    def _match_args_filter(self, match_args_line):
        """This function is used to do a pre-treatment for the match_args_line."""
        filter_lines = []
        double_quote_count = 0
        double_quote_exclude_count = 0
        for line in match_args_line.split("\n"):
            match = re.match("(.*)\s+#(.*)", line)
            if match:
                left_line = match.group(1)
                double_quote_count += len(re.findall(r'"', left_line))
                double_quote_exclude_count += len(re.findall(r"\\\"", left_line))
                if (double_quote_count - double_quote_exclude_count) % 2 != 0:
                    right_line = match.group(2)
                    double_quote_count += len(re.findall(r'"', right_line))
                    double_quote_exclude_count += len(re.findall(r"\\\"", right_line))
                    filter_lines.append(line)
                else:
                    filter_lines.append(left_line)
            else:
                filter_lines.append(line)

        return "\n".join(filter_lines)

    def loading_cmakelists(self, cmakelist_path, parent_info=None):
        """Loading CMakeLists.txt or *.cmake files"""
        if not os.path.exists(cmakelist_path):
            return False
        with open(cmakelist_path, "r") as cmake_fin:
            data = cmake_fin.read()
            data = data.lstrip(" \t\n")
        cmake_path = os.path.dirname(cmakelist_path)
        if not os.path.isabs(cmake_path):
            cmake_path = os.path.join(self._project_path, cmake_path)

        self._add_default_value(cmakelist_path, parent_info=parent_info)
        one_cmake_info = self._cmake_info.get(cmakelist_path, dict())
        options = list()
        reverses = list()
        for command_name, args_line in cmake_command_analyzer.get_cmake_command(data, cmake_path, one_cmake_info):
            logger.debug(command_name)
            if not self.command_regex.match(command_name + "("):
                # pass commands we don't care about
                continue
            analyzer = cmake_command_analyzer.get_command_analyzer(command_name)
            filter_args_line = self._match_args_filter(args_line)
            analyzer(filter_args_line, one_cmake_info, options, reverses)
        logger.info("Complete analyzing CMakeLists: %s." % cmakelist_path)
        return

    def loading_project_cmakelists(self):
        top_level_cmakelists = os.path.join(self._project_path, "CMakeLists.txt")
        if not os.path.exists(top_level_cmakelists):
            logger.warning("Not found %s, stop cmake project analysis." % top_level_cmakelists)

        cmakelists_queue = queue.Queue()
        cmakelists_queue.put((top_level_cmakelists, None))
        is_empty = False
        while not is_empty:
            try:
                (filename, parent_info) = cmakelists_queue.get(block=False)
            except queue.Empty:
                is_empty = True
                continue
            try:
                self.loading_cmakelists(filename, parent_info)
                one_cmake_info = self._cmake_info.get(filename, dict())
                subdirectories = one_cmake_info.get("subdirectories", list())
                [cmakelists_queue.put((os.path.join(subdirectory, "CMakeLists.txt"), one_cmake_info)) \
                 for subdirectory in subdirectories]
            except capture_util.ParserError:
                logger.warning("%s analysis fail!" % filename)

        logger.info("Complete project analysis.")
        return

    def dump_config_h(self):
        """If there is a config.h file need to generate, it will be serialized here."""
        pass

    def build_cmake_target(self, cmakelist_path, one_cmake_info):
        dir_name = os.path.dirname(cmakelist_path)
        # 1. Loading global defined definitions, includes, flags.
        # generating from option.
        global_definition_dict = one_cmake_info.get("definitions", dict())
        global_definitions_list = []
        for defineds in get_variable_value_with_option("definitions", one_cmake_info,
                                                       global_definition_dict, var_place=None):
            global_definitions_list.append(defineds)

        # Directly use all option level defined value, don't care about option.
        global_include_dict = one_cmake_info.get("includes", dict())
        global_includes = get_variable_value_without_option(global_include_dict, one_cmake_info)
        global_includes_list = [global_includes, ]
        global_includes_line = " ".join(map("-I{}".format, global_includes))

        # used defined part, don't care option.
        global_flag_dict = one_cmake_info.get("flags", dict())
        global_flags = get_variable_value_without_option(global_flag_dict, one_cmake_info)
        global_flags_list = [global_flags, ]

        # 2. Loading global, directory, source scope properties.

        # 3. Loading target properties.
        # TODO: If we can specify sources, we can build it by target, but now we just use all target properties.
        for target_key, target in one_cmake_info.get("target", dict()).items():
            target_definitions_list = []
            target_flags_list = []
            if "COMPILE_DEFINITIONS" in target:
                for defineds in get_variable_value_with_option("COMPILE_DEFINITIONS", one_cmake_info,
                                                                target.get("COMPILE_DEFINITIONS", dict()),
                                                               var_place=["target", target_key]):
                    target_definitions_list.append(defineds)
            if "COMPILE_FLAGS" in target:
                for flags in get_variable_value_with_option("COMPILE_FLAGS", one_cmake_info,
                                                            target.get("COMPILE_FLAGS", dict()),
                                                            var_place=["target", target_key]):
                    target_flags_list.append(flags)

            if len(target.get("files", list())) != 0:
                files = target.get("files", list())
                # Avoid unknown list contains list problem
                move_to_top = lambda x: (z for y in x for z in (isinstance(y, list) and move_to_top(y) or [y]))
                files = list(move_to_top(files))
            else:
                files = []
                for file_name in os.listdir(dir_name):
                    file_path = os.path.join(dir_name, file_name)
                    if os.path.isfile(file_path):
                        files.append(file_name)

            sub_files = []
            for file_line in files:
                sub_files.extend(re.split(r"\s+", file_line))

            c_files = filter(lambda file_name: True if file_name.split(".")[-1] == "c" else False,
                             sub_files)
            cxx_files = filter(lambda file_name: True if file_name.split(".")[-1] in \
                                                         ["cxx", "cpp", "cc"] else False, sub_files)
            target["c_files"] = list(c_files)
            target["cxx_files"] = list(cxx_files)

            logger.info("# Get case from files.")
            c_case = None
            cxx_case = None
            if "c_files" in target and len(target.get("c_files", list())) != 0:
                c_files = target.get("c_files", list())
                idx = random.randint(0, len(c_files) - 1)
                c_case = c_files[idx]
                # c_case = os.path.join(dir_name, c_files[idx])
            if "cxx_files" in target and len(target.get("cxx_files", list())) != 0:
                cxx_files = target.get("cxx_files", list())
                idx = random.randint(0, len(cxx_files) - 1)
                cxx_case = cxx_files[idx]
                # cxx_case = os.path.join(dir_name, cxx_files[idx])

            if c_case is None and cxx_case is None:
                continue

            all_definitions = []
            for global_definitions in global_definitions_list:
                for target_definitions in target_definitions_list:
                    all_definitions.append(global_definitions + target_definitions)

            all_flags = []
            for target_flags in target_flags_list:
                all_flags.append(target_flags + global_flags)

            c_compiler_status = False
            cxx_compiler_status = False
            for definitions in all_definitions:
                for flags in all_flags:
                    for compiler_type in ("C", "CXX"):
                        print("Mark ---- -- - - -- - ")
                        print(definitions)
                        print(flags)
                        print("Mark2 ---- -- - - -- - ")
                        compiler = self.c_compiler if compiler_type == "C" else self.cxx_compiler
                        case = c_case if compiler_type == "C" else cxx_case
                        flags_type = "c_flags" if compiler_type == "C" else "cxx_flags"

                        if case is None:
                            if compiler_type == "C":
                                c_compiler_status = True
                            else:
                                cxx_compiler_status = True
                            continue
                        definition_line = " ".join(map("-D{}".format, definitions))
                        flag_line = " ".join(flags)
                        cmd = "{} -c {} -o {} {} {} {}".format(
                            compiler, os.path.join(dir_name, case), os.path.join(self._build_path, c_case + ".o"),
                            global_includes_line, definition_line, flag_line
                        )
                        logger.debug(cmd)
                        (returncode, out, err) = capture_util.subproces_calling(cmd, dir_name)
                        if returncode == 0:
                            logger.info("Try compile for target: %s success." % target_key)
                            target[flags_type] = {
                                "definitions": definitions,
                                "includes": global_includes,
                                "flags": flags,
                            }
                            target["directory"] = dir_name
                            if compiler_type == "C":
                                c_compiler_status = True
                            else:
                                cxx_compiler_status = True
                    if c_compiler_status and cxx_compiler_status:
                        break
                if c_compiler_status and cxx_compiler_status:
                    break

    def build_all_cmake_target(self):
        """Generate all target of the defined source and undefined source."""
        for (cmakelist_path, one_cmake_info) in self._cmake_info.items():
            self.build_cmake_target(cmakelist_path, one_cmake_info)
        return

    def try_build_target(self, cmake_file_path, files=None, c_compiler="cc", cxx_compiler="g++"):
        """Attempt to use compiler flags to compile a case, if it pass, we can use the present macros flags."""
        pass

    def try_build_all_cmake_target(self, c_compiler="cc", cxx_compiler="g++"):
        """Iteratively determining all target flags, and also define flags for left source files."""
        pass


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
