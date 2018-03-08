# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: m4_macros_analysis.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-06 10:12:11
    @LastModif: 2018-03-06 20:12:02
    @Note:
"""
import sys
import ply.lex as lex
import re
import types
from ply.lex import TOKEN


# TODO: 对于其他的语法不做关注，只关注变量的变化，和某些语句，如AC_SUBST， AC_CONDITIONAL等导出环境的语句
# 我们甚至不关心变量在判断和case中怎么变化了，干脆这找到-D的情况，只获取含有-D的变化情况
# 对于扫描到MACROS 和 VAR的行，我们需要重新解析，否则，可能会出现错误

reserved = {
    "if": "if",
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
        print "macros line: {}".format(t.value)
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
        print "Illegal character '%s'" % t.value[0]
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

# string 表示接下来的东西除了 ] 全部不管，作为一个字符串输出
# default 表示采用默认方式解析
# bool值代表是否必须
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


def check_next(generator, string):
    try:
        token = generator.next()
    except StopIteration:
        raise ParserError
    if token.type == string:
        return True
    raise ParserError


# 代表没有解析到目标的token，解析异常
class ParserError(Exception):
    def __init__(self, message=None):
        if message:
            self.args = (message,)
        else:
            self.args = ("Parser Error happen!",)


def analyze(generator, analysis_type="default", func_name=None, level=0):
    print "# calling analysis with type: " + analysis_type + " In function: " + func_name + "\tlevel:" + str(level)
    quote_count = 0
    start_tokens = [generator.next() for _ in range(2)]
    print start_tokens
    if start_tokens[0].type == "LSPAREN" and start_tokens[1].type == "LSPAREN":
        # Double quote include data is code for c/c++ which is used to automatically generate new source file.
        # So we skip them here.
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
    elif start_tokens[0].type != "LSPAREN":
        raise ParserError

    generator.seek(generator.index - 1)
    quote_count += 1
    token = generator.next()

    if analysis_type == "default":
        # Count of quotes, if quote_count == 0, it means the process main back to last recursion
        while quote_count != 0:
            print quote_count
            # 1. Analyze some defined function from m4_macros_map
            if token.type == "ID" and token.value in m4_macros_map:
                print "## Start defined function analysis\tname: " + token.value
                check_next(generator, "LPAREN")
                for i in xrange(len(m4_macros_map[token.value]) / 2):
                    print "comma: " + str(i)

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
                            print "defined next_token: %s" % next_token
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

                if token.type == "RSPAREN":
                    break

            elif token.type == "ID" and re.match("^A[CM]_", token.value):
                # 2. Analyze some undefined functions started with AC | AM.
                #   Using "default" mode.
                print "## Start undefined function analysis\tname: " + token.value
                check_next(generator, "LPAREN")
                analyze(generator, analysis_type="default", func_name=func_name, level=level + 1)

                try:
                    next_token = generator.next()
                    print "mark1: %s" % next_token
                    while next_token.type == "COMMA":
                        analyze(generator, analysis_type="default", func_name=func_name, level=level + 1)
                        next_token = generator.next()
                        print "markN: %s" % next_token
                except StopIteration:
                    raise ParserError

                if next_token.type != "RPAREN":
                    raise ParserError
                token = generator.next()
                if token.type == "RSPAREN":
                    break

            elif token.type == "ID":
                # 3. Analyze some assignment line, and skip some line we don't care.
                print "## Start unknown line analysis %s" % token
                next_token = generator.next()
                if next_token.type == "ASSIGN" or next_token.type == "APPEND":
                    value = cache_check_assign(generator)
                    print value
                    if value is not None:
                        # TODO: 修改变量
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
                        print "AAA : %s" % next_token
                        token = next_token

                if token.type == "RSPAREN":
                    break

            elif token.type == "MACROS":
                # 4. Analyze Macros assignment line.
                print "## Start Macros line analysis %s" % token
                line = token.value
                macros_line = re.compile(r"")
                token = generator.next()
                print token
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
        print "## Start string analysis"
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
        print "## Start test analysis"
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
                "option": [],
                "is_replace": True,
            }
        export_vars[token.value] = 1
        token = generator.next()
        print token

    elif analysis_type == "ID_VAR":
        # TODO:需要后面重建
        export_vars[token.value] = None
        token = generator.next()

    if token.type == "RSPAREN":
        print "### END CALLING: %s" % token
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


def cache_check_assign(generator):
    """Assignment or appendage line analysis."""
    index = generator.index
    value = ""
    try:
        next_token = generator.next()
        print "======%s" % next_token
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
            data = self._generator.next()
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
                data = self._generator.next()
                self._caches.append(data)
            except StopIteration:
                self._has_next = False
                if self._index == len(self._caches) + 1:
                    raise StopIteration
        data = self._caches[self._index - 1]
        self._index += 1
        self._set_max()
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
