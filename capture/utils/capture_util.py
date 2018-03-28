# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: capture_util.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-12 10:53:39
    @LastModif: 2018-03-12 10:55:18
    @Note:
"""

import subprocess
import logging
import re

logger = logging.getLogger("capture")


def_escape = {' ': '\\ ',
              '\\': '\\\\',
              '(': '\\(',
              ')': '\\)',
              '<': '\\<',
              '>': '\\>',
              '\'': '\\\'',
              '\"': '\\\"',
              '{': '\\{',
              '}': '\\}',
              '[': '\\[',
              ']': '\\]',
              ',': '\\,',
              ';': '\\;',
              ':': '\\:',
              '?': '\\?',
              '`': '\\`',
              '!': '\\!',
              '@': '\\@',
              '#': '\\#',
              '$': '\\$',
              '%': '\\%',
              '^': '\\^',
              '&': '\\&',
              '*': '\\*',
              '|': '\\|',
              '-': '\\-',
              '+': '\\+'
              }


def subproces_calling(cmd="", cwd=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT):
    try:
        logger.debug("Excute command: %s" % cmd)
        if cwd:
            p = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=stdout, stderr=stderr)
        else:
            p = subprocess.Popen(cmd, shell=True, stdout=stdout, stderr=stderr)

        out, err = p.communicate()
        return p.returncode, out, err
    except (OSError, ValueError, subprocess.TimeoutExpired):
        logger.warning("Subprocess command:[%s] execute fail" % cmd)
        return -1, None, None


def replace_escape(string):
    output_string = string
    for key, value in def_escape.items():
        output_string = output_string.replace(key, value)

    return output_string


def undefined_split(line, info_dict=None):
    """
    A split util function for cutting undefined line into pieces.
    :param line:            A string contains of undefined var.
    :param info_dict:       Checking dict for checking variable value.
    :return:
    """
    if info_dict is None:
        info_dict = dict()
    dollar_var_pattern = r"(.*)\$[\({]([a-zA-Z_][a-zA-Z0-9_]*)[\)}](.*)"
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
    idx = 0
    while idx != -1:
        if idx >= len(slices):
            idx = -1
        else:
            slice = slices[idx]
            if len(slice) == 0:
                slices.pop(idx)
                continue
            idx += 1
    return slices


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


def strip_quotes(s):
    if s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    elif s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    else:
        return s


# Analysis Error happen
class ParserError(Exception):
    def __init__(self, message=None):
        if message:
            self.args = (message,)
        else:
            self.args = ("Parser Error happen!",)


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
