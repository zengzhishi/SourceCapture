# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_autotools.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-01 16:50:58
    @LastModif: 2018-03-01 16:50:58
    @Note: TODO: Analyze autotools config files.
"""

import imp
import types
import os
import sys
import re
import queue
import copy
import random

if __name__ == "__main__":
    import m4_macros_analysis
    import capture_util
else:
    import capture.utils.m4_macros_analysis as m4_macros_analysis
    import capture.utils.capture_util as capture_util

import logging
sys.path.append(os.path.join("..", "conf"))
import parse_logger
parse_logger.addFileHandler("./capture.log", "capture")
logger = logging.getLogger("capture")


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

# M4_MACROS_ARGS_COUNT = {
#     # function_name, args_count
#     "AC_DEFUN": ["default", "default"],
#     "AC_MSG_CHECKING": ["str"],
#     "AC_MSG_RESULT": ["str"],
#     "AC_MSG_ERROR": ["str"],
#     "AC_COMPILE_IFELSE": ["shell", "shell", "shell"],
#     "AC_REQUIRE": ["name"]
# }

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


assignment_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*=\s*(.*)")
appendage_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*\+=\s*(.*)")

# remove [ -o ] witch maybe not present in Makefile.am flags
filename_flags = ["-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]

preset_output_variables = [
    "CXXFLAGS",
    "CFLAGS",
    "CPPFLAGS",
    "OBJCFLAGS",
    "OBJCXXFLAGS",
    "LIBS",
    "LDFLAGS",
]


def _check_undefined(slices):
    for slice in slices:
        if re.search(r"\$\(?[a-zA-Z_][a-zA-Z0-9_]*\)?", slice) or \
                re.search(r"\@[a-zA-Z_][a-zA-Z0-9_]\@", slice):
            return True
    return False


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


def sort_flags_line(flags, reverse=False):
    if not isinstance(reverse, bool):
        logger.warning("Unknown reverse flag use, use default reverse: %s" % reverse)
        reverse = False
    regex = re.compile(r"\s+-D[a-z_A-Z][a-zA-Z0-9_]*")
    sorted_flags = sorted(flags, key=lambda line: len(regex.findall(line)), reverse=reverse)
    return sorted_flags


class AutoToolsParser(object):
    _fhandle_configure_ac = None

    def __init__(self, project_path, output_path, build_path=None):
        self._project_path = project_path
        self._output_path = output_path

        self._build_path = build_path if build_path else self._project_path
        self.configure_ac_info = {}
        self.m4_macros_info = {}
        self.makefile_am_info = {}

    def __del__(self):
        if self._fhandle_configure_ac:
            self._fhandle_configure_ac.close()

    @property
    def build_path(self):
        return self._build_path

    @property
    def project_path(self):
        return self._project_path

    def dump_makefile_am_info(self, output_path=None):
        if output_path:
            dump_data(self.makefile_am_info, output_path)
        else:
            dump_data(self.makefile_am_info, os.path.join(self._output_path, "am_info.json"))

    def try_build_target(self, makefile_path, files=[]):
        """可以在这里构建一个比较简单的格式返回"""
        if len(self.makefile_am_info.get(makefile_path, dict())) == 0:
            return
        make_info = self.makefile_am_info.get(makefile_path, dict())
        path = os.path.dirname(makefile_path)
        if "target" in make_info:
            targets = make_info.get("target", dict())
            for target_key, target in targets.items():
                # Build files
                if len(target.get("files", list())) != 0:
                    files = target.get("files", list())
                    # Avoid unknown list contains list problem
                    move_to_top = lambda x: (z for y in x for z in (isinstance(y, list) and g(y) or [y]))
                    files = list(move_to_top(files))
                    for file_line in files:
                        sub_files = re.split(r"\s+", file_line)
                        c_files = filter(lambda file_name: True if file_name.split(".")[-1] == "c" else False,
                                           sub_files)
                        cpp_files = filter(lambda file_name: True if file_name.split(".")[-1] in \
                                                                     ["cxx", "cpp", "cc"] else False, sub_files)
                        target["c_files"] = list(c_files)
                        target["cpp_files"] = list(cpp_files)
                # Get test case
                c_case = None
                cpp_case = None
                if "c_files" in target and len(target.get("c_files", list())) != 0:
                    c_files = target.get("c_files", list())
                    idx = random.randint(0, len(c_files))
                    c_case = os.path.join(path, c_files[idx])
                if "cpp_files" in target and len(target.get("cpp_files", list())) != 0:
                    cpp_files = target.get("cpp_files", list())
                    idx = random.randint(0, len(cpp_files))
                    cpp_case = os.path.join(path, cpp_files[idx])

                # Try build
                if c_case is None and cpp_case is None:
                    return
                else:
                    if "flags" not in target:
                        target["c_flags"] = []
                        target["cpp_flags"] = []
                        continue
                    for flag_name, flags in target["flags"]:
                        if flag_name == "CFLAGS":
                            # 1. 排序，根据-D参数数目由 小到大
                            # 2. 切分，将 flags切分成 macros 和 includes 和 other
                            # 3. 组成 info_dict 返回
                            sorted_flags = sort_flags_line(flags)
                            for line in sorted_flags:
                                words = split_line(line)

                                temp = ""
                                for (i, word) in enumerate(words):
                                    temp = temp + " " + word if temp else word
                                    if i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-':
                                        continue

                                    pass

                                    temp = ""

                    pass

    def dump_m4_info(self, output_path=None):
        if output_path:
            dump_data(self.m4_macros_info, output_path)
        else:
            dump_data(self.m4_macros_info, os.path.join(self._output_path, "m4_info.json"))

    def dump_ac_info(self, output_path=None):
        if output_path:
            dump_data(self.configure_ac_info, output_path)
        else:
            dump_data(self.configure_ac_info, os.path.join(self._output_path, "configure_ac_info.json"))

    def set_makefile_am(self, project_scan_result):
        """
        :param project_scan_result:                     project scan result from source_detective
        :return:
        """
        for file_path in project_scan_result:
            fhandle_am = open(file_path, "r")
            self.makefile_am_info[file_path] = {
                "variables": {
                    # Set builtin preset variables for Makefile.am analysis
                    "top_srcdir": {
                        "defined": [self._project_path,],
                        "undefined": [],
                        "is_replace": False,
                        "option": {}
                    },
                    "top_builddir": {
                        "defined": [self._build_path,],
                        "undefined": [],
                        "is_replace": False,
                        "option": {}
                    },
                },
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
                    am_pair_var[key] = {
                        "defined": [],
                        "undefined": [],
                        "is_replace": False,
                        # Represent whether to replace variable's value here. For default_N, it may be always True.
                        "option": {}
                    }

                words = split_line(value)

                present_option_dict = self._get_option_level_dict(am_pair_var[key], options, is_in_reverse,
                                                                  True if assig_match else False)
                present_option_dict["is_replace"] = True if assig_match else False
                present_option_dict["defined"] = present_option_dict["defined"] if append_match else []
                present_option_dict["undefined"] = present_option_dict["undefined"] if append_match else []

                temp = ""
                for (i, word) in enumerate(words):
                    temp = temp + " " + word if temp else word
                    if i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-':
                        continue

                    slices = self._undefined_split(temp, am_pair_var)

                    transfer_word = "".join(slices)
                    if m4_macros_analysis.check_undefined(slices, with_ac_var=True):
                        if m4_macros_analysis.check_undefined_self(slices, key):
                            present_option_dict["is_replace"] = False
                            # The empty assignment string, causing no change for variable.
                            if len(slices) == 1:
                                temp = ""
                                continue
                        present_option_dict["undefined"].append(transfer_word)
                    else:
                        present_option_dict["defined"].append(transfer_word)

                    temp = ""

            # Loading include Makefile.inc
            include_regex = re.compile("^include\s+(.*)")
            include_match = include_regex.match(line)
            if include_match:
                folder = os.path.sep.join(fhandle_am.name.split(os.path.sep)[:-1])
                include_path = os.path.join(folder, include_match.group(1))
                self._loading_include(am_pair_var, include_path, options, is_in_reverse)

    def _undefined_split(self, line, info_dict=None):
        if info_dict is None:
            info_dict = dict()
        dollar_var_pattern = r"(.*)\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)(.*)"
        at_var_pattern = r"(.*)\@([a-zA-Z_][a-zA-Z0-9_]*)\@(.*)"
        with_var_line_regex = re.compile(dollar_var_pattern + r"|" + at_var_pattern)

        with_var_line_match = with_var_line_regex.match(line)
        # slices will be a reversed list
        slices = []
        while with_var_line_match:
            match_chose = 0
            if with_var_line_match.group(1) is None:
                match_chose += 3

            line = with_var_line_match.group(1 + match_chose)
            undefine_var = with_var_line_match.group(2 + match_chose)
            other = with_var_line_match.group(3 + match_chose)
            if undefine_var in info_dict:
                value = info_dict[undefine_var]
                if len(value["undefined"]) == 0 and value["option"] is None:
                    undefine_var = " ".join(value["defined"]) if len(value["defined"]) != 0 else ""
                    line = line + undefine_var + other
                elif value["option"] is None:
                    slices.append(other)
                    slices.append(value["defined"])
                    slices.append(value["undefined"])
                else:
                    slices.append(other)
                    if match_chose == 0:
                        slices.append("$({})".format(undefine_var))
                    else:
                        slices.append("@{}@".format(undefine_var))
            else:
                slices.append(other)
                if match_chose == 0:
                    slices.append("$({})".format(undefine_var))
                else:
                    slices.append("@{}@".format(undefine_var))
            with_var_line_match = with_var_line_regex.match(line)
        slices.append(line)
        slices.reverse()
        return slices

    def _loading_include(self, am_pair_var, include_path, options, is_in_reverse):
        with open(include_path, "r") as include_fin:
            self._reading_makefile_am(am_pair_var, include_fin, options, is_in_reverse)

    def _check_global_dict_empty(self, dict):
        default_n_regex = re.compile(r"default_\d+")
        default_N = 1
        for option_key in dict["option"].keys():
            if default_n_regex.match(option_key):
                default_N += 1
        if len(dict["defined"]) != 0 or len(dict["undefined"]) != 0 or len(dict["option"]) != 0:
            return True, default_N
        return False, 0

    def _check_option_dict_empty(self, dict):
        if len(dict["defined"]) != 0 or len(dict["undefined"]) != 0 or len(dict["option"]) != 0:
            return True
        return False

    def _get_option_level_dict(self, start_dict, options, is_in_reverse, is_assign):
        present_dict = start_dict
        has_default, default_N = self._check_global_dict_empty(present_dict)
        if len(options) == 0 and is_assign and has_default:
            # for default_N option, False will not be used.
            present_dict["option"]["default_" + default_N] = {
                True: {"defined": [], "undefined": [], "option": {}, "is_replace": True},
                False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
            }
            present_dict = present_dict["option"]["default_%d" % default_N][True]
        for option, reverse_stat in zip(options, is_in_reverse):
            if option not in present_dict["option"]:
                present_dict["option"][option] = {
                    True: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                    False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                }
            present_dict = present_dict["option"][option][not reverse_stat]
        return present_dict

    def set_configure_ac(self):
        if self._fhandle_configure_ac is None:
            config_file_name = self._check_configure_scan()
            if config_file_name:
                self._fhandle_configure_ac = open(config_file_name, "r")
            else:
                logger.warning("Not found configure.ac or configure.in file")
                return

        import imp
        imp.reload(m4_macros_analysis)

        func_name = "configure_ac"
        m4_macros_analysis.functions[func_name] = {
           "calling": [],
           "need_condition_var": [],
           "need_assign_var": [],
           "variables": {},
           # when program meet AC_SUBST, we will move variable from dict["variables"] to "export_variables" after
           "export_variables": {},
           "export_conditions": {}
        }
        try:
            raw_data = self._fhandle_configure_ac.read()
        except IOError:
            logger.warning("Couldn't read configure.ac file")
            return
        mylexer = m4_macros_analysis.M4Lexer()
        mylexer.build()
        generator = mylexer.get_token_iter(raw_data)
        cache_generator = m4_macros_analysis.CacheGenerator(generator, origin_data=raw_data)
        # self.m4_macros_info = m4_macros_analysis.functions_analyze(cache_generator)
        try:
            # initialize functions
            m4_macros_analysis.analyze(cache_generator, func_name=func_name,
                                       analysis_type="default", level=1, allow_defunc=True,
                                       allow_calling=True)
        except StopIteration:
            self.configure_ac_info = m4_macros_analysis.functions
            logger.info("Reading '%s' complete." % self._fhandle_configure_ac.name)

    def _check_configure_scan(self):
        for file_name in CONFIGURE_AC_NAMES:
            file_path = os.path.join(self._project_path, file_name)
            if os.path.exists(file_path):
                return file_path
        return None

    def _preload_m4_config(self, configure_ac_filepath):
        cmd = "fgrep \"{}\" {}".format("AC_CONFIG_MACRO_DIR", configure_ac_filepath)
        (returncode, out, err) = capture_util.subproces_calling(cmd)

        if returncode == 0:
            macros_dir_match = macros_dir_regex.match(out.decode("utf8"))
            if not macros_dir_match:
                logger.warning("Not match AC_CONFIG_MACRO_DIR in {}!".format(configure_ac_filepath))
                m4_folders = None
            else:
                m4_folders = macros_dir_match.group(1)
        else:
            logger.warning("cmd: {}, exec fail!".format(cmd))
            m4_folders = None
        return m4_folders

    def _get_m4_folder(self):
        if "macros_dir" not in self.configure_ac_info:
            config_file_name = self._check_configure_scan()
            if config_file_name:
                self._fhandle_configure_ac = open(config_file_name, "r")
                self.configure_ac_info["macros_dir"] = self._preload_m4_config(config_file_name)
            else:
                logger.warning("Not found configure.ac or configure.in file")
                return None

        return self.configure_ac_info["macros_dir"]

    def _m4_file_analysis(self, fin):
        """Loading m4 file, and building an info map."""
        # imp.reload(m4_macros_analysis)
        raw_data = fin.read()
        mylexer = m4_macros_analysis.M4Lexer()
        mylexer.build()
        lexer = mylexer.clone()
        generator = mylexer.get_token_iter(raw_data, lexer=lexer)
        cache_generator = m4_macros_analysis.CacheGenerator(generator, origin_data=raw_data)
        self.m4_macros_info = m4_macros_analysis.functions_analyze(cache_generator, fin.name)
        return

    def load_m4_macros(self):
        """Loading m4 files from m4 directory, and building up macros info table."""
        m4_folder_name = self._get_m4_folder()
        if not m4_folder_name:
            logger.warning("Not found m4 folder.")
            return

        m4_project = os.path.join(self._project_path, m4_folder_name)
        for file_name in os.listdir(m4_project):
            if not file_name.endswith(".m4"):
                continue
            file_path = os.path.join(m4_project, file_name)
            with open(file_path) as m4_fin:
                self._m4_file_analysis(m4_fin)

        # Setup m4 lib for configure.ac to use
        m4_macros_analysis.m4_libs = self.m4_macros_info
        logger.info("m4 files loading complete.")

    def build_ac_export_infos(self):
        """利用variables构建export_variables"""
        if not self.configure_ac_info:
            return
        export_variables = self.configure_ac_info["configure_ac"]["export_variables"]
        variables = self.configure_ac_info["configure_ac"]["variables"]
        for export_var in export_variables:
            src = variables.get(export_var, dict())
            dest = export_variables.get(export_var, dict())
            if len(src) == 0:
                continue

            if len(dest.get("defined", [])) != 0 or len(dest.get("undefined"), []) != 0:
                continue

            export_variables[export_var] = src

        for preset_export_var in preset_output_variables:
            if preset_export_var in export_variables:
                continue

            src = variables.get(preset_export_var, dict())
            if len(src) == 0:
                continue

            export_variables[preset_export_var] = src

    def build_autotools_target(self):
        """利用 ac infos 和 am infos来构建最终目标的flags"""
        # Step 1. Check out whether is a root_path makefile.am
        root_path_makefile = os.path.join(self._project_path, "Makefile.am")
        if root_path_makefile in self.makefile_am_info:
            makefile_am = self.makefile_am_info.get(root_path_makefile, dict())
            # step 1.1. check subdir
            subdirs = makefile_am["variables"].get("SUBDIRS", list())
            sub_makefile_ams = map(lambda subpath: os.path.join(self._project_path, subpath), subdirs)
        else:
            sub_makefile_ams = self.makefile_am_info.keys()

        logger.info("sub makefile am: %s" % sub_makefile_ams)
        # Step 2. Check subdir makefile.am
        for makefile_am in sub_makefile_ams:
            am_infos = self.makefile_am_info.get(makefile_am, dict())
            am_pair_var = am_infos.get("variables", dict())

            # Step 2.1. Get targets we need.
            program_regex = re.compile(r".+_PROGRAMS")
            lib_regex = re.compile(r".+_LIBRARIES")
            libtool_regex = re.compile(r".+_LTLIBRARIES")

            am_infos["target"] = {}
            target = am_infos["target"]
            # Step 2.2 search building final target
            for (key, value) in am_pair_var.items():
                if program_regex.match(key):
                    print("?????")
                    if len(am_pair_var[key].get("option", dict())) == 0:
                        program_gen = self._get_am_value(key, am_pair_var, am_pair_var[key])
                        for program_list in program_gen:
                            for program in program_list:
                                program = program.replace(".", "_")
                                target[program] = {"type": "program"}

                elif lib_regex.match(key):
                    if len(am_pair_var[key].get("option", dict())) == 0:
                        lib_gen = self._get_am_value(key, am_pair_var, am_pair_var[key])
                        for lib_list in lib_gen:
                            for lib in lib_list:
                                lib = lib.replace(".", "_")
                                target[lib] = {"type": "lib"}

                elif libtool_regex.match(key):
                    if len(am_pair_var[key].get("option", dict())) == 0:
                        libtool_gen = self._get_am_value(key, am_pair_var, am_pair_var[key])
                        for libtool_list in libtool_gen:
                            for libtool in libtool_list:
                                libtool = libtool.replace(".", "_")
                                target[libtool] = {"type": "libtool"}

                else:
                    continue

            # Step 2.4 Find concentrated target configure variables.
            flags_suffix = [
                "CPPFLAGS",
                "CFLAGS",
                "CXXFLAGS",
            ]
            logger.info("Checking target variable key.")
            for target_key in target.keys():
                # 2.4.1 Find sources files
                key = target_key + "_SOURCES"
                logger.info(key)
                if key not in am_pair_var:
                    #TODO: 考虑将当前目录下的文件使用这个
                    sources = []
                else:
                    sources = []
                    for lines in self._get_am_value(key, am_pair_var, am_pair_var[key]):
                        sources.extend(lines)
                logger.info(sources)

                # 2.4.2 Find flags
                # Temporarily we don't need to use it.
                key = target_key + "_LDFLAGS"
                logger.info(key)
                ld_flags = []
                if key in am_pair_var:
                    for lines in self._get_am_value(key, am_pair_var, am_pair_var[key]):
                        ld_flags.extend(lines)
                logger.info(ld_flags)

                final_flags = {}
                for suffix in flags_suffix:
                    key = target_key + "_" + suffix
                    logger.info("#Next key: %s" % key)
                    flags = []
                    if key not in am_pair_var:
                        continue
                    # Iterator each probability
                    for lines in self._get_am_value(key, am_pair_var, am_pair_var[key]):
                        flags.append(lines)
                    logger.info(flags)
                    final_flags[suffix] = flags

                # files may contain include files.
                target[target_key]["files"] = sources
                target[target_key]["flags"] = final_flags
                target[target_key]["ld_flags"] = ld_flags

    def _get_am_value(self, variable, am_pair_var, option_dict):
        """Try to get value of one variable."""
        logger.info("# Start check value: %s" % variable)
        if variable not in am_pair_var:
            yield [""]

        undefineds = option_dict.get("undefined", list())
        defineds = option_dict.get("defined", list())
        options = option_dict.get("option", dict())
        if len(options) != 0:
            for final_var_tuple in self._option_builder(option_dict):
                final_var_dict = self._merge_option(option_dict, dict())
                for opt, level in final_var_tuple:
                    final_var_dict = self._merge_option(opt, final_var_dict)
                logger.info("final_var_dict: %s" % final_var_dict)
                undefineds = final_var_dict.get("undefined", list())
                defineds = final_var_dict.get("defined", list())

                if len(undefineds) == 0:
                    yield defineds
                else:
                    # Local ${} variable has been checking in local variables.
                    # Here we need to check preset_variables and ac_subst variables.
                    for undefined_line in self._undefined_builder(final_var_dict, am_pair_var):
                        copy_defineds = copy.deepcopy(defineds)
                        copy_defineds.append(undefined_line)
                        yield copy_defineds
        else:
            if len(undefineds) == 0:
                yield defineds
            else:
                for undefined_line in self._undefined_builder(option_dict, am_pair_var):
                    copy_defineds = copy.deepcopy(defineds)
                    copy_defineds.append(undefined_line)
                    yield copy_defineds

    def _undefined_builder(self, var_dict, am_pair_var=None, ac_pair_var=None):
        """
            When we calling undefined builder we have been complete top level option check.
            TODO: 将这个函数修改为同时适用于 ac 部分的 variable 构建
        """
        first_queue = queue.Queue()
        second_queue = queue.Queue()

        line = " ".join(var_dict.get("undefined", list()))
        slices = self._undefined_split(line, am_pair_var)
        first_queue.put(["",])

        dollar_var_pattern = r"\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)"
        at_var_pattern = r"\@([a-zA-Z_][a-zA-Z0-9_]*)\@"
        var_regex = re.compile(dollar_var_pattern + r"|" + at_var_pattern)
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
            if not var_match:
                missions.append(slice)
                next_q.put(missions)
            else:
                export_var_flag = True if var_match.group(2) is not None else False
                var_name = var_match.group(2) if export_var_flag else var_match.group(1)

                configure_ac_dict = self.configure_ac_info.get("configure_ac", dict())
                ac_export_vars = configure_ac_dict.get("export_variables", dict())

                if var_name not in am_pair_var and var_name in ac_export_vars:
                    # builtin preset variables.
                    for defined_list in self._get_ac_value(var_name):
                        value = " ".join(defined_list)
                        temp_missions = copy.deepcopy(missions)
                        temp_missions.append(value)
                        next_q.put(temp_missions)
                elif var_name in am_pair_var:
                    for defined_list in self._get_am_value(var_name, am_pair_var, am_pair_var[var_name]):
                        value = " ".join(defined_list)
                        temp_missions = copy.deepcopy(missions)
                        temp_missions.append(value)
                        next_q.put(temp_missions)
                else:
                    # Unknown variable.
                    value = ""
                    missions.append(value)
                    next_q.put(missions)

        result_queue = first_queue if level % 2 == 0 else second_queue
        while not result_queue.empty():
            try:
                result_slices = result_queue.get(block=False)
                yield "".join(result_slices)
            except queue.Empty:
                continue

    def _option_builder(self, var_dict):
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

        new_var_dict = self._merge_option(var_dict, dict())
        for key in options_key:
            new_var_dict["option"][key] = options.get(key, dict())
        missions = [(new_var_dict, 0)]
        q.put(missions)

        # Start iterating all level option
        complete = False
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
                if "option" not in mission[0] and True in mission[0]:
                    # option level
                    true_missions = missions[:i]
                    true_opt = mission[0].get(True, dict())
                    true_missions.append((true_opt, level + 1))
                    true_missions.extend(missions[i + 1:])

                    false_missions = missions[:i]
                    false_opt = mission[0].get(False, dict())
                    false_missions.append((false_opt, level + 1))
                    false_missions.extend(missions[i + 1:])

                    q.put(true_missions)
                    q.put(false_missions)
                    option_check_flag = False
                    break

                if "option" in mission[0]:
                    # var_dict level
                    options = var_dict.get("option", dict())
                    option_keys = options.keys()
                    if len(option_keys) != 0:
                        start_missions = missions[:i]
                        for option in options:
                            option_dict = options[option]
                            start_missions.append((option_dict, level))
                        start_missions.extend(missions[i + 1:])
                        q.put(start_missions)
                        option_check_flag = False
                        break
            # Checking return type
            if len(missions) != 0 and option_check_flag:
                yield missions

    def _merge_option(self, src_option, dest_option):
        result_option = {
            "defined": copy.deepcopy(dest_option.get("defined", list())),
            "undefined": copy.deepcopy(dest_option.get("undefined", list()))
        }

        for defined in src_option.get("defined", list()):
            if defined not in result_option.get("defined", list()):
                result_option["defined"].append(defined)

        for undefined in src_option.get("undefined", list()):
            if undefined not in result_option.get("undefined", list()):
                result_option["undefined"].append(undefined)

        result_option["option"] = dest_option.get("option", dict())
        return result_option

    def _get_ac_value(self, variable):
        """
            Maybe should be a recursion generator.
            To simplify ac_value gain yield times, macros line will be the only concentrated probability.
            TODO: 获取 configure.ac 中的export的变量
            包含了preset的变量，和使用SUBST导出的变量
        """
        yield []


def unbalanced_quotes(s):
    single = 0
    double = 0
    excute = 0
    for c in s:
        if c == "'":
            single += 1
        elif c == '"':
            double += 1
        if c == "`":
            excute += 1

    move_double = s.count('\\"')
    move_single = s.count("\\'")
    single -= move_single
    double -= move_double

    is_half_quote = single % 2 == 1 or double % 2 == 1 or excute % 2 == 1
    return is_half_quote


if __name__ == "__main__":
    if len(sys.argv) == 3:
        project_path = sys.argv[1]
        am_path = sys.argv[2]
    else:
        sys.stderr.write("Fail! Please input path and am path.\n")
        exit(-1)

    make_file_am = [
        am_path,
    ]

    auto_tools_parser = AutoToolsParser(project_path, os.path.join("..", "..", "result"))
    # auto_tools_parser.load_m4_macros()
    # auto_tools_parser.set_configure_ac()
    auto_tools_parser.set_makefile_am(make_file_am)
    auto_tools_parser.build_autotools_target()
    auto_tools_parser.try_build_target(make_file_am[0])

    auto_tools_parser.dump_makefile_am_info()

    # auto_tools_parser.dump_m4_info()
    #
    # auto_tools_parser.dump_ac_info()


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
