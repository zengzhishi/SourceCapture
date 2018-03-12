# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: m4_macros_analysis.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-06 10:12:11
    @LastModif: 2018-03-06 20:12:02
    @Note:
"""
from __future__ import absolute_import

import sys
import ply.lex as lex
import re
import types
import logging

sys.path.append("../capture/conf")
import parse_logger
logger = logging.getLogger("capture")


# TODO: 对于其他的语法不做关注，只关注变量的变化，和某些语句，如AC_SUBST， AC_CONDITIONAL等导出环境的语句
# 我们甚至不关心变量在判断和case中怎么变化了，干脆这找到-D的情况，只获取含有-D的变化情况
# 对于扫描到MACROS 和 VAR的行，我们需要重新解析，否则，可能会出现错误

reserved = {
    "if": "if",
    "else": "else",
    "elif": "elif",
    "test": "test",
    "then": "then",
    "fi": "fi",
    "case": "case",
    "in": "in",
    "esac": "esac"
}


class M4Lexer(object):
    # List of token names.
    tokens = [
        "MACROS",
        "VAR",

        "QUE_MARK",
        'COLON',
        'DOUBLE_SEMICOLON',         # for case seperating
        'SEMICOLON',
        'MINUS',
        'COMMENT',

        'LPAREN',
        'LSPAREN',
        'LBRACES',
        'RPAREN',
        'RSPAREN',
        'RBRACES',

        'COMMA',
        'POINT',
        'QUOTE',
        'DOUBLE_QUOTE',
        'START',

        'EQUAL',
        'ASSIGN',
        'APPEND',
        'CASE_OR',
        'AND',
        'OR',
        'NUMBER',
        'ID',
    ] + list(reserved.values())

    t_VAR = r'\$\(?[a-zA-Z_][a-zA-Z0-9_]*\)?'
    t_QUE_MARK = r'\?'
    t_COLON = r':'
    t_DOUBLE_SEMICOLON = r';;'
    t_SEMICOLON = r';'
    t_MINUS = r'-'
    t_LPAREN = r'\('
    t_RPAREN = r'\)'
    t_LSPAREN = r'\['
    t_RSPAREN = r'\]'
    t_LBRACES = r'\{'
    t_RBRACES = r'\}'
    t_COMMA = r','
    t_START = r'\*'
    t_POINT = r'\.'
    t_QUOTE = r"'"
    t_DOUBLE_QUOTE = r'"'
    t_CASE_OR = r'\|'
    t_AND = r'&&'
    t_OR = r'\|\|'
    t_EQUAL = r'\=\='
    t_APPEND = r'\+\='
    t_ASSIGN = r'\='
    t_NUMBER = r'\d+\.?\d*'

    t_ignore = ' \t'

    def t_MACROS(self, t):
        r'.*\=.*\-D\$?\(?[a-zA-Z_][a-zA-Z0-9_].*'
        print("macros line: {}".format(t.value))
        return t

    def t_COMMENT(self, t):
        r'\#.*|dnl.*'
        pass    # ignore comment line

    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    def t_ID(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_]*'
        t.type = reserved.get(t.value, 'ID') # if in reserved, use own type, else use ID
        return t

    def t_error(self, t):
        print("Illegal character '%s'" % t.value[0])
        t.lexer.skip(1)

    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    # Test it output
    def get_token_iter(self, data):
        self.lexer.input(data)
        while True:
            tok = self.lexer.token()
            if not tok: break
            yield tok


functions = {}

export_vars = {}

export_conditions = {}

# string: Means that we don't care about content, just concentrate on ']'
# default: Using default method to analyze token flow.
# call_function: Means that we will calling other function here.
# ID_VAR & ID_VAR: Means the field content one ID. ID_VAR will export variable, ID_ENV will export condition.

# The bool value represent whether this field is essential.
# TODO: 拓展表格，加入可能会出现的 IFELSE 宏定义函数，这种情况的话应该作为option来处理, 条件解析不出来就直接构建一个随机不重复的条件
m4_macros_map = {
    "AC_REQUIRE": ["call_function", True],
    "AC_MSG_CHECKING": ["string", True],
    "AC_MSG_RESULT": ["string", True],
    "AC_MSG_ERROR": ["string", True],
    "AC_SUBST": ["ID_VAR", True, "string", False],
    "AM_CONDITIONAL": ["ID_ENV", True, "test", False],
}

left = ['LPAREN', 'LSPAREN', 'LBRACES',]
right = ['RPAREN', 'RSPAREN', 'RBRACES',]


filename_flags = ["-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]


def check_next(generator, string):
    try:
        token = generator.next()
    except StopIteration:
        raise ParserError
    if token.type == string:
        return True
    raise ParserError


def try_next(generator, string):
    if not generator.has_next():
        return False
    token = generator.next()
    if token.type == string:
        return True
    generator.seek(generator.index - 1)
    return False


def _check_undefined(slices):
    for slice in slices:
        if re.search(r"\$\(?[a-zA-Z_][a-zA-Z0-9_]*\)?", slice):
            return True
    return False


def _check_undefined_self(slices, self_var):
    for slice in slices:
        search = re.search(r"\$\(?([a-zA-Z_][a-zA-Z0-9_]*)\)?", slice)
        if search:
            append_var = search.group(1)
            if append_var == self_var:
                return True
    return False


# 代表没有解析到目标的token，解析异常
class ParserError(Exception):
    def __init__(self, message=None):
        if message:
            self.args = (message,)
        else:
            self.args = ("Parser Error happen!",)


options = []
reverses = []


def _check_bool_expresion(generator):
    # TODO: 结束条件可以是两种： ; | then, 最终generator停止应该在 then
    # 返回选择条件, 粗暴处理

    option_list = []
    try:
        token = generator.next()
        if token.type != "test" and token.type != "LSPAREN":
            raise ParserError
        while token.type != "then":
            if token.type != "SEMICOLON":
                option_list.append(token.value)
            token = generator.next()
    except StopIteration:
        raise ParserError
    return " ".join(option_list)


def _check_sh_if(generator, level, func_name=None):
    option = _check_bool_expresion(generator)
    options.append(option)
    reverses.append(False)
    end_flags = False
    while not end_flags:
        # TODO: 可以是一个default解析, 需要添加新的结束条件 else | elif | fi
        analyze(generator, analysis_type="default", func_name=func_name,
                level=level + 1, ends=["else", "elif", "fi"])
        generator.seek(generator.index - 1)
        token = generator.next()
        if token.type == "fi":
            options.pop()
            reverses.pop()
            end_flags = True
        elif token.type == "else":
            reverses[-1] = True
        elif token.type == "elif":
            option = _check_bool_expresion(generator)
            options[-1] = option
            reverses[-1] = False
        else:
            raise ParserError
    return


def _cache_check_assign(generator):
    """Assignment or appendage line analysis."""
    index = generator.index
    value = ""
    try:
        next_token = generator.next()
        if next_token.type == "DOUBLE_QUOTE":
            # 赋值语句
            next_token = generator.next()
            while next_token.type != "DOUBLE_QUOTE":
                value += " " + next_token.value
                next_token = generator.next()
        else:
            generator.seek(index)
            return None
        return value
    except StopIteration:
        raise ParserError


def _check_global_dict_empty(dict):
    default_n_regex = re.compile(r"default_\d+")
    default_N = 1
    for option_key in dict["option"].keys():
        if default_n_regex.match(option_key):
            default_N += 1
    if len(dict["defined"]) != 0 or len(dict["undefined"]) != 0 or len(dict["option"]) != 0:
        return True, default_N
    return False, 0


def _get_present_level_dict(start_dict, is_assign=False):
    present_dict = start_dict
    has_default, default_N = _check_global_dict_empty(present_dict)

    if len(options) == 0 and is_assign and has_default:
        # for default_N option, False will not be used.
        present_dict["option"]["default_%d" % default_N] = {
            True: {"defined": [], "undefined": [], "option": {}, "is_replace": True},
            False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
        }
        present_dict = present_dict["option"]["default_%d" % default_N][True]

    for option, reverse_stat in zip(options, reverses):
        if option not in present_dict["option"]:
            present_dict["option"][option] = {
                True: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
            }
        present_dict = present_dict["option"][option][not reverse_stat]
    return present_dict


def analyze(generator, analysis_type="default", func_name=None, level=0, ends=["RSPAREN",]):
    logger.info("# calling analysis with type: " + analysis_type +
                " In function: " + func_name + "\tlevel:" + str(level))
    quote_count = 0
    try:
        start_tokens = [generator.next() for _ in range(2)]
    except StopIteration:
        raise ParserError
    if start_tokens[0].type == "LSPAREN" and start_tokens[1].type == "LSPAREN":
        # Double quote include data is code for c/c++ which is used to automatically generate new source file.
        # Because we don't care about them, we skip them here.
        quote_count += 2
        token = generator.next()
        while quote_count != 0:
            token = generator.next()
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1
        if token.type == "RSPAREN":
            return
        else:
            raise ParserError
    elif len(ends) != 1:
        pass
    elif start_tokens[0].type != "LSPAREN" and len(ends) == 1:
        # TODO: 这里其实还可能是不规范的写法，没有使用 [] 来括起一个参数域，这种情况属于不规范的方式，
        # 但是autotools可以解析，需要保持兼容
        raise ParserError

    if start_tokens[0].type == "LSPAREN":
        generator.seek(generator.index - 1)
        quote_count += 1
        token = generator.next()
    else:
        generator.seek(generator.index - 2)
        token = generator.next()

    if analysis_type == "default":
        # Count of quotes, if quote_count == 0, it means the process main back to last recursion
        while quote_count != 0 or token not in ends:
            # 1. Analyze some defined function from m4_macros_map
            if token.type == "ID" and token.value in m4_macros_map:
                logger.info("## Start defined function analysis\tname: " + token.value)
                check_next(generator, "LPAREN")
                for i in range(len(m4_macros_map[token.value]) // 2):
                    name = m4_macros_map[token.value][i * 2]
                    is_essential = m4_macros_map[token.value][i * 2 + 1]

                    if is_essential:
                        if i != 0:
                            check_next(generator, "COMMA")
                        analyze(generator, analysis_type=name, func_name=func_name, level=level + 1)
                    else:
                        try:
                            next_token = generator.next()
                            if next_token.type == "COMMA":
                                next_token = generator.next()
                            logger.info("defined next_token: %s" % next_token)
                        except StopIteration:
                            raise ParserError

                        if next_token.type != "LSPAREN":
                            generator.seek(generator.index - 1)
                            break
                        else:
                            generator.seek(generator.index - 1)
                            analyze(generator, analysis_type=name, func_name=func_name, level=level + 1)
                check_next(generator, "RPAREN")
                token = generator.next()
                print(token)

                if token.type == "RSPAREN":
                    break

            elif token.type == "ID" and re.match("^A[CM]_", token.value):
                # 2. Analyze some undefined functions started with AC | AM.
                #   Using "default" mode.
                logger.info("## Start undefined function analysis\tname: " + token.value)
                check_next(generator, "LPAREN")
                analyze(generator, analysis_type="default", func_name=func_name, level=level + 1)

                try:
                    next_token = generator.next()
                    while next_token.type == "COMMA":
                        analyze(generator, analysis_type="default", func_name=func_name, level=level + 1)
                        next_token = generator.next()
                except StopIteration:
                    raise ParserError

                if next_token.type != "RPAREN":
                    raise ParserError
                token = generator.next()
                if token.type == "RSPAREN":
                    break

            elif token.type in ends:
                break

            elif token.type == "ID":
                # 3. Analyze some assignment line, and skip some line we don't care.
                logger.info("## Start unknown line analysis %s" % token)
                var = token.value
                next_token = generator.next()
                if next_token.type == "ASSIGN" or next_token.type == "APPEND":
                    is_assign = True if next_token.type == "ASSIGN" else False
                    value = _cache_check_assign(generator)
                    if value is not None:
                        # TODO: 修改变量
                        # if var not in functions[func_name]["variables"]:
                        #     functions[func_name]["variables"][var] = {
                        #         "defined": [],
                        #         "undefined": [],
                        #         "option": [],
                        #         "is_replace": True,
                        #     }
                        # start_dict = functions[func_name]["variables"][var]
                        pass
                    token = generator.next()
                else:
                    sub_quote_count = 0
                    lineno = token.lineno
                    # When start a new line, we should end up this loop.
                    while (next_token.type != 'RSPAREN' or sub_quote_count != 0) and \
                            next_token.lineno == lineno:
                        if next_token.type in left:
                            sub_quote_count += 1
                        if next_token.type in right:
                            sub_quote_count -= 1
                        try:
                            next_token = generator.next()
                        except StopIteration:
                            raise ParserError
                        token = next_token

                if token.type == "RSPAREN":
                    break

            elif token.type == "MACROS":
                # 4. Analyze Macros assignment line.
                logger.info("## Start Macros line analysis %s" % token)
                line = token.value

                macros_assignment_line_regex = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\"?([^\"]*)\"?")
                macros_appendage_line_regex = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\+=\s*\"?([^\"]*)\"?")
                with_var_line_regex = re.compile(r"(.*)\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)(.*)")

                assign_match = macros_assignment_line_regex.match(line)
                append_match = macros_appendage_line_regex.match(line)
                variables = functions[func_name]["variables"]
                if assign_match or append_match:
                    var = assign_match.group(1) if assign_match else append_match.group(1)
                    value = assign_match.group(2) if assign_match else append_match.group(2)
                    if var not in variables:
                        variables[var] = {
                            "defined": [],
                            "undefined": [],
                            "option": {},
                            "is_replace": True if assign_match else False
                        }

                    present_option_dict = _get_present_level_dict(variables[var], True if assign_match else False)
                    present_option_dict["is_replace"] = True if assign_match else False
                    present_option_dict["defined"] = present_option_dict["defined"] if append_match else []
                    present_option_dict["undefined"] = present_option_dict["undefined"] if append_match else []

                    words = split_line(value)
                    temp = ""
                    for (i, word) in enumerate(words):
                        temp = temp + " " + word if temp else word
                        if i != len(words) - 1 and word in filename_flags and words[i + 1][0] != '-':
                            continue

                        with_var_line_match = with_var_line_regex.match(temp)
                        slices = []
                        while with_var_line_match:
                            temp = with_var_line_match.group(1)
                            undefine_var = with_var_line_match.group(2)
                            other = with_var_line_match.group(3)
                            if undefine_var in variables:
                                value = variables[undefine_var]
                                if len(value["undefined"]) == 0 and len(value["option"]) == 0:
                                    undefine_var = " ".join(value["defined"]) if len(value["defined"]) != 0 else ""
                                    temp = temp + undefine_var + other
                                elif len(value["option"]) == 0:
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
                        # TODO: 尚未添加 option 的处理
                        if _check_undefined(slices):
                            if _check_undefined(slices):
                                present_option_dict["is_replace"] = False
                                if len(slices) == 1:
                                    temp = ""
                                    continue
                            present_option_dict["undefined"].append(transfer_word)
                        else:
                            present_option_dict["defined"].append(transfer_word)

                        temp = ""

                token = generator.next()
                if token.type == "RSPAREN":
                    break

            elif token.type == "if":
                _check_sh_if(generator, level, func_name=func_name)
                token = generator.next()
                if token.type == "RSPAREN":
                    break

            elif token.type in left:
                quote_count += 1
                token = generator.next()
            elif token.type in right:
                quote_count -= 1
                token = generator.next()
            else:
                # 4. Start with some undefined token, we maybe skip it.
                # TODO: 这里缺少了对 if test ... 和 case 的处理
                token = generator.next()

    elif analysis_type == "string":
        logger.info("## Start string analysis")
        quote_count = 0
        while token.type != "RSPAREN" or quote_count != 0:
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1
            try:
                token = generator.next()
            except StopIteration:
                raise ParserError

    elif analysis_type == "test":
        logger.info("## Start test analysis")
        while token.type != "RSPAREN":
            token = generator.next()

    elif analysis_type == "call_function":
        if token.type == "ID":
            functions[func_name]["calling"].append(token.value)
        else:
            raise ParserError
        token = generator.next()

    elif analysis_type == "ID_ENV":
        if token.value not in functions[func_name]["variables"]:
            functions[func_name]["variables"][token.value] = {
                "defined": [],
                "undefined": [],
                "option": {},
                "is_replace": True,
            }
        export_conditions[token.value] = 1
        token = generator.next()

    elif analysis_type == "ID_VAR":
        # TODO:需要后面重建
        export_vars[token.value] = {
            "defined": [],
            "undefined": [],
            "option": {},
            "is_replace": True
        }
        token = generator.next()

    # if token.type == "RSPAREN":
    if token.type in ends:
        logger.info("### END CALLING: %s" % token)
        return
    else:
        raise ParserError


def functions_analyze(generator):
    # This function will analyze token flow and concentrates on AC_DEFUN
    while generator.has_next():
        try:
            token = generator.next()
            if token.type == "ID" and token.value == "AC_DEFUN":
                check_next(generator, "LPAREN")
                check_next(generator, "LSPAREN")
                token = generator.next()
                if token.type != "ID":
                    raise ParserError
                func_name = token.value
                functions[func_name] = {
                    "calling": [],
                    "variables": {}
                }
                check_next(generator, "RSPAREN")
                check_next(generator, "COMMA")
                analyze(generator, analysis_type="default", func_name=func_name, level=1)
                check_next(generator, "RPAREN")
            else:
                raise ParserError
        except StopIteration:
            raise ParserError


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


class CacheGenerator(object):
    """
        If we use has_next() to check next token exist, we will not meet StopIteration exception.
        Anyway, this class is used to store history token, and provide function seek back old tokens.
        TODO: We can add more features like getting same feature cluster.
    """
    _max_index = 0
    _index = 0
    _caches = []
    _has_next = True

    def __init__(self, generator):
        if type(generator) != types.GeneratorType:
            raise TypeError
        self._generator = generator

        try:
            data = next(self._generator)
            self._caches.append(data)
            self._index += 1
            self._set_max()
        except StopIteration:
            self._has_next = False

    def _set_max(self):
        if self._index > self._max_index:
            self._max_index = self._index

    @property
    def index(self):
        return self._index

    def next(self):
        if self._index == self._max_index:
            try:
                data = next(self._generator)
                self._caches.append(data)
            except StopIteration:
                self._has_next = False
                if self._index == len(self._caches) + 1:
                    raise StopIteration
        data = self._caches[self._index - 1]
        self._index += 1
        self._set_max()
        print(data)
        return data

    def seek(self, index=0):
        if index > self._max_index:
            self._index = self._max_index
        else:
            self._index = index

    def has_next(self):
        if self._index < self._max_index:
            return True
        elif self._index == self._max_index and self._has_next:
            return True
        else:
            return False


if __name__ == "__main__":
    filename = sys.argv[1]
    with open(filename) as fin:
        raw_data = fin.read()
    mylexer = M4Lexer()
    mylexer.build()
    generator = mylexer.get_token_iter(raw_data)
    cache_generator = CacheGenerator(generator)
    functions_analyze(cache_generator)
    import json

    with open("./data_func.out", "w") as fout:
        json.dump(functions, fout, indent=4)

    with open("./data_var.out", "w") as fout2:
        json.dump(export_vars, fout2, indent=4)


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
