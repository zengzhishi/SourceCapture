# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_make.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-02-02 14:25:36
    @LastModif: 2018-02-02 14:26:29
    @Note:  make以及gcc命令的解析
"""

import os
import re
import subprocess


DEFAULT_MAKEFILE_NAME = [
    "Makefile",
    "makefile",
    "GNUMakefile"
]


# 使用 make -qp 获取执行的编译命令， 在修改Makefile 执行伪目标获取参数的方法
def create_data_base_infos(root_path, output, makefile_name="Makefile", make_args=None):
    """
    创建info文件
    :param root_path:
    :param output_path:
    :param makefile_name:
    :param make_args:
    :return:
    """
    make_file = root_path + os.path.sep + makefile_name
    if not os.path.exists(make_file):
        raise IOError("No Makefile in " + root_path)

    cmd = "make -qp "
    if make_args:
        cmd += make_args

    p = subprocess.Popen(cmd, shell=True, cwd=root_path,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = p.communicate()
    output.writelines(out)
    return output


def block_read(fin):
    # 去掉block前的空行
    line = fin.readline()
    while not line.strip("\n"):
        line = fin.readline()
    # 存储block的数据
    lines = []
    while line.strip("\n") != "":
        lines.append(line.strip("\n"))
        line = fin.readline()
    return lines


def search_target_line(lines):
    """如果有多个配置行，获取EXTRA config，并找到target line"""
    pravite_config_lines = []
    for line in lines:
        config_line_match = re.match("^\w+.*\s*:\s*", line)
        if config_line_match:
            pravite_config_lines.append(line)
    if len(pravite_config_lines) > 1:
        for i in range(len(pravite_config_lines) - 1):
            line = lines[i]
            target, config = re.split("\s*:\s*", line)
            configs = re.split("")


def analysis_block(lines):
    """
    解析块行的配置,得到目标文件所需要的参数
    :param lines:
    :return:
    """
    target_line = 0
    # 非目标, 可能是依赖文件或内置对象
    if lines[0] == "# Not a target:":
        return {}
    elif lines[0] == '# makefile (from \'Makefile\'':
        # 可能会导致问题
        target_line += 1

    if target_line != 0:
        target_line = search_target_line(lines)
        target, depend = re.split("\s*:\s*", lines[target_line])
    if len(depend) == 0:
        # 伪目标, 暂时先不管, 后面有需要再完成
        params_dict = {}
    else:
        targets = re.split("\s+", target)
        depends = re.split("\s+", depend)
        params_dict = {
            "target": targets,
            "depends": depends,
            "auto_params": {},
            "commands": [],
            "need_params": {}
        }
        for line in lines:
            auto_param_match = re.match("(.*)\s+\:=\s+(.*)", line)
            if auto_param_match:
                key = auto_param_match.group(1)[2:]
                params_dict["auto_params"][key] = auto_param_match.group(2)
                continue
            if line[0] == "\t":
                # for command line
                line_data = line.strip("\t")
                lst = re.split("\s+", line_data)
                params_dict["commands"].append(lst)
                for slice in lst:
                    args = re.findall(r"\$\((\w+)\)", slice)
                    if len(args):
                        for arg in args:
                            params_dict["need_params"][arg] = ""
    return params_dict


def print_info_analysis(output_path, targets=None):
    """
    解析文件的内容, 获取目标文件所需要的参数
    :param output_path:
    :param targets: 如果为None, 则默认把所有非伪目标的编译命令参数都获取回来
    :return:
    """
    fin = open(output_path + "/make_info.txt", "r")
    all_need_params = []
    all_params_dicts = []
    line = fin.readline()
    while line != '':
        # 1. 先找到目标行
        while line.strip("\n") != '# Files':
            line = fin.readline()
        # 2. 开始读取配置块
        lines = block_read(fin)
        while lines[-1] != "# VPATH Search Paths":
            # 3. 解析块
            config_param = analysis_block(lines)
            if len(config_param) == 0:
                # 非目标
                pass
            else:
                # 目标
                all_params_dicts.append(config_param)
                for arg in config_param["need_params"]:
                    all_need_params.append(arg)
            lines = block_read(fin)
        # 3. Files区读取完毕,继续跳过
    return all_params_dicts, all_need_params


def modify_makefile(echo_args, root_path,
                    makefile, new_makefile, phony_target="capture_echo_values"):
    """
    复制原来的makefile, 并将参数输出的伪目标语句加入到新的Makefile中, 形成新的makefile
    :param echo_args:
    :param root_path:
    :param makefile:
    :param new_makefile:
    :param phony_target:
    :return:
    """
    pass


def exec_makefile(new_makefile, field_name):
    """
    执行修改之后的makefile的伪目标, 并将参数的结果解析之后返回
    :param new_makefile:
    :param field_name:
    :return:
    """
    pass


def check_makefile(build_path, makefile_name=None):
    is_exist = False
    if not makefile_name:
        for makefile_name in DEFAULT_MAKEFILE_NAME:
            make_file = build_path + os.path.sep + makefile_name
            if os.path.exists(make_file):
                is_exist = True
                break
        if not is_exist:
            raise IOError("No Makefile in " + build_path)
    else:
        make_file = build_path + os.path.sep + makefile_name
        if not os.path.exists(make_file):
            raise IOError("No Makefile in " + build_path)

    return is_exist


# 使用 make -Bnkw 方式获取编译命令的方法
def create_command_infos(logger, build_path, output, makefile_name=None,
                 make_args=""):
    make_file = makefile_name
    try:
        is_exist = check_makefile(build_path, makefile_name)
    except IOError:
        raise

    if is_exist:
        cmd = "cd {}; make -Bnkw {}".format(build_path, make_args)
    else:
        cmd = "cd {}; make -Bnkw -f {} {}".format(build_path, make_file, make_args)

    logger.info("execute command: " + cmd)
    p = subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = p.communicate()
    output.writelines(out)
    return output


def split_cmd_line(line):
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

    # 去除转义后的引号带来的影响
    move_double = s.count('\\"')
    move_single = s.count("\\'")
    single -= move_single
    double -= move_double

    is_half_quote = single % 2 == 1 or double % 2 == 1 or excute % 2 == 1
    return is_half_quote


def strip_quotes(s):
    if s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    elif s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    else:
        return s


def excute_quote_code(s, build_dir):
    s_regax = re.match("`(.*)`(.*)", s)
    excute_cmd = "cd {}; {}".format(build_dir, s_regax.group(1))
    p = subprocess.Popen(excute_cmd, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = p.communicate()
    value = out.strip("\n") + s_regax.group(2)
    return value


def parse_flags(logger, build_log_in, build_dir,
                other_cc_compiles=None, other_cxx_compiles=None):
    skip_count = 0
    # Setting compiler regex string
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

    # Leverage make --print-directory option
    make_enter_dir = re.compile("^\s*make\[\d+\]: Entering directory [`\'\"](?P<dir>.*)[`\'\"]\s*$")
    make_leave_dir = re.compile("^\s*make\[\d+\]: Leaving directory .*$")

    # Flags we want:
    # TODO: We can add more falgs patten
    # -includes (-i, -I)
    # -warnings (-Werror), but no assembler, etc. flags (-Wa,-option)
    # -language (-std=gnu99) and standard library (-nostdlib)
    # -defines (-D)
    # -m32 -m64
    # -g
    flags_whitelist = [
        "-c",
        "-g",
        "-m.+",
        "-W[^,]*",
        "-[iIDF].*",
        "-std=[a-z0-9+]+",
        "-(no)?std(lib|inc)",
        "-D([a-zA-Z0-9_]+)=(.*)"
    ]
    flags_whitelist = re.compile("|".join(map("^{}$".format, flags_whitelist)))

    # Used to only bundle filenames with applicable arguments
    filename_flags = ["-o", "-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]
    invalid_include_regex = re.compile("(^.*out/.+_intermediates.*$)|(.+/proguard.flags$)")

    file_regex = re.compile("(^.+\.c$)|(^.+\.cc$)|(^.+\.cpp$)|(^.+\.cxx$)")

    compile_db = []
    line_count = 0

    dir_stack = [build_dir]
    working_dir = build_dir

    # Process build log
    for line in build_log_in:
        # Concatenate line if need
        accumulate_line = line
        while line.endswith('\\\n'):
            accumulate_line = accumulate_line[:-2]
            line = next(build_log_in, '')
            accumulate_line += line
        line = accumulate_line

        # Parse directory that make entering/leaving
        enter_dir = make_enter_dir.match(line)
        if make_enter_dir.match(line):
            working_dir = enter_dir.group('dir')
            dir_stack.append(working_dir)
        elif make_leave_dir.match(line):
            dir_stack.pop()
            working_dir = dir_stack[-1]

        if cc_compile_regex.match(line):
            compiler = 'C'
        elif cpp_compile_regex.match(line):
            compiler = 'CXX'
        else:
            continue

        arguments = []
        words = split_cmd_line(line)[1:]
        filepath = None
        line_count += 1

        for (i, word) in enumerate(words):
            if word[0] == '`':
                word = excute_quote_code(word, working_dir)

            if word == "-c":
                continue

            if (file_regex.match(word)):
                filepath = word

            if(word[0] != '-' or not flags_whitelist.match(word)):
                # phony target
                word_strip_quotes = strip_quotes(word)
                if word_strip_quotes[0] == '-' and flags_whitelist.match(word_strip_quotes):
                    # transfer equal value to double quotes
                    quetos_words = split_cmd_line(word_strip_quotes)
                    if len(quetos_words) > 1:
                        for (i, quetos_word) in enumerate(quetos_words):
                            if quetos_word[i] in filename_flags and quetos_word[1][0] != '-':
                                w = quetos_words[i + 1]
                                if w[0] == '/':
                                    p = w
                                else:
                                    p = os.path.abspath(working_dir + os.path.sep + w)
                                if not invalid_include_regex.match(p):
                                    if quetos_word == "-I":
                                        arguments.append(quetos_word + p)
                                    else:
                                        arguments.append("{} {}".format(quetos_word, p))
                    else:
                        if word_strip_quotes.startswith("-I"):
                            opt = word[0:2]
                            val = word[2:]
                            if val[0] == '/':
                                p = val
                            else:
                                p = os.path.abspath(working_dir + os.path.sep + val)
                            if not invalid_include_regex.match(p):
                                arguments.append(opt + p)
                        elif word_strip_quotes.startswith("-D"):
                            definition_with_value = re.compile("^-D([a-zA-Z0-9_]+)=(.*)$")
                            definition_with_value_match = definition_with_value.match(word_strip_quotes)
                            if definition_with_value_match:
                                key = definition_with_value_match.group(1)
                                value = definition_with_value_match.group(2)
                                value = "'{}'".format(value)
                                word_strip_quotes = "-D{}={}".format(key, value)
                            arguments.append(word_strip_quotes)
                continue

            # include arguments for this option, if there are any, as a tuple
            if(i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-'):
                w = words[i + 1]
                # p = w if inc_prefix is None else os.path.join(inc_prefix, w)
                if w[0] == '/' or words[i] == "-include":
                    p = w
                else:
                    p = os.path.abspath(working_dir + os.path.sep + w)
                if not invalid_include_regex.match(p):
                    if word == "-I":
                        arguments.append(word + p)
                    else:
                        arguments.append("{} {}".format(word, p))
            else:
                if word.startswith("-I"):
                    opt = word[0:2]
                    val = word[2:]
                    # p = val if inc_prefix is None else os.path.join(inc_prefix, val)
                    if val[0] == '/':
                        p = val
                    else:
                        p = os.path.abspath(working_dir + os.path.sep + val)
                    if not invalid_include_regex.match(p):
                        arguments.append(opt + p)
                else:
                    arguments.append(word)

        if filepath is None:
            logger.warning("Empty file name. Ignoring: {}".format(line))
            skip_count += 1
            continue

        # logger.info("args={} --> {}".format(len(arguments), filepath))
        # arguments.append(filepath)
        # TODO performance: serialize to json file here?
        compile_db.append({
            'directory': working_dir,
            'file': filepath,
            'arguments': arguments,
            'compiler': compiler
        })

    return line_count, skip_count, compile_db

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
