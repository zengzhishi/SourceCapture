# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_scons.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-02-27 16:32:04
    @LastModif: 2018-02-27 16:32:04
    @Note:
"""

import os
import re
import copy
import capture.utils.parse_make as parse_make
import capture.utils.capture_util as capture_util
import logging


logger = logging.getLogger("capture")
DEFAULT_SCONSTRUCT_NAME = "SConstruct"


def has_file_s(line):
    file_regex = re.compile("(^.+\.c$)|(^.+\.cc$)|(^.+\.cpp$)|(^.+\.cxx$)")
    words = line.strip().split("\t ")
    for w in words:
        if file_regex.match(w):
            return True
    return False


def check_command_format(result, other_cc_compiles=None, other_cxx_compiles=None):
    """Checking the present subprocess calling output are the correct format we need."""
    cc_re_compile_str = "(.*-?g?cc )|(.*-?clang )"
    if other_cc_compiles:
        for cc_compile in other_cc_compiles:
            cc_re_compile_str += "|(.*-?" + cc_compile + ' )'
    cxx_re_compile_str = "(.*-?[gc]\+\+ )|(.*-?clang\+\+ )"
    if other_cxx_compiles:
        for cxx_compile in other_cxx_compiles:
            # Maybe have some problem
            if cxx_compile[-2:] == "++":
                cxx_compile.replace('++', '\\+\\+')
            cxx_re_compile_str += "|(.*-?" + cxx_compile + ' )'
    cc_compile_regex = re.compile(cc_re_compile_str)
    cpp_compile_regex = re.compile(cxx_re_compile_str)
    for line in result.split(b"\n"):
        line = line.decode("utf8")
        if (cc_compile_regex.match(line) or cpp_compile_regex.match(line)) \
                and has_file_s(line):
            return True
        else:
            continue
    return False


def check_sconstruct_exist(build_path):
    build_file = build_path + os.path.sep + DEFAULT_SCONSTRUCT_NAME
    return os.path.exists(build_file)


def create_command_infos(build_path, output, origin_verbose_list, build_args=""):
    """
    Use try-match to checking which is the useful dry-run verbose.
    :param build_path:                              project building path.
    :param output:                                  result and temp data output path.
    :param origin_verbose_list:                     the origin verbose name list.
    :param build_args:                              scons command execution arguments.
    :return:
    """
    is_exist = check_sconstruct_exist(build_path)
    if not is_exist:
        logger.warning("There is no SConstruct in %s" % build_path)
        return None

    has_verbose = False
    outlines = None

    verbose_list = copy.copy(origin_verbose_list)
    # TODO: Move these flag list to config file.
    for value in ("1", "True", "true", "TRUE", "ON", "on"):
        verbose_list += list(map(lambda verbose: "{}={}".format(verbose, value), origin_verbose_list))

    for verbose in verbose_list:
        cmd = "scons -n {} {}".format(build_args, verbose)
        (returncode, out, err) = capture_util.subproces_calling(cmd, cwd=build_path)

        if check_command_format(out):
            has_verbose = True
            outlines = out.decode("utf-8")
            break
        logger.info("scons verbose name [%s] check fail." % verbose)
        logger.debug("SCons Build fail info: %s" % out)

    if has_verbose:
        output.write(outlines)
    return output


def parse_flags(build_log_in, build_dir,
                other_cc_compiles=None, other_cxx_compiles=None):
    """Compiler commands analysis may be similar process with make -n"""
    return parse_make.parse_flags(build_log_in, build_dir,
                                  other_cc_compiles, other_cxx_compiles)


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
