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
from ply.lex import TOKEN


# TODO: 对于其他的语法不做关注，只关注变量的变化，和某些语句，如AC_SUBST， AC_CONDITIONAL等导出环境的语句
# 我们甚至不关心变量在判断和case中怎么变化了，干脆这找到-D的情况，只获取含有-D的变化情况
# 对于扫描到MACROS 和 VAR的行，我们需要重新解析，否则，可能会出现错误

reserved = {
    "ac_defun": "AC_DEFUN",
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
        'RPAREN',
        'RSPAREN',
        'LBRACES',
        'RBRACES',

        'COMMA',
        'POINT',
        'QUOTE',
        'DOUBLE_QUOTE',
        'START',

        'EQUAL',
        'ASSIGN',
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
    t_ASSIGN = r'\='
    t_NUMBER = r'\d+\.?\d*'

    t_ignore = ' \t'

    def t_MACROS(self, t):
        r'.*\=.*\-D\$?\(?[a-zA-Z_][a-zA-Z0-9_].*'
        print "macros line: {}".format(t.value)
        return t

    def t_COMMENT(self, t):
        r'^\#.*|dnl.*'
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


functions = {

}

# string 表示接下来的东西除了 ] 全部不管，作为一个字符串输出
# default 表示采用默认方式解析
# 大写的对象则表示目标是获取到这个类型的数据，且只有一个
# bool值代表是否必须
m4_macros_map = {
    "AC_DEFUN": ["ID", True, "default", True],
    "AC_REQUIRE": ["ID", True],
    "AC_MSG_CHECKING": ["string", True],
    "AC_MSG_RESULT": ["string", True],
    "AC_MSG_ERROR": ["string", True],
    "AC_SUBST": ["ID", True, "string", False],
    "AM_CONDITIONAL": ["ID", True, "test", False],
}


def check_next(generator, string):
    try:
        token = generator.next()
    except StopIteration:
        return False
    if token.type == string:
        return True
    return False


class ParserError(Exception):
    def __init__(self, message, s):
        self.args = (message,)
        self.text = s


def analyze(generator, analysis_type="default"):
    token = generator.next()
    # 括号统计，如果 < 0 则返回， 代表要收束到上一个递归
    quote_count = 0
    while token:
        if analysis_type == "default":
            if token.type == "AC_DEFUN" and token.value not in functions:
                functions[token.value] = {}

            if token.type in m4_macros_map:
                for i in xrange(len(m4_macros_map[token.type]) / 2):
                    name = m4_macros_map[i * 2]
                    is_essential = m4_macros_map[i * 2 + 1]
                    if is_essential:
                        if not check_next(generator, "LPAREN"):
                            raise ParserError
                        if not check_next(generator, "LSPAREN"):
                            raise ParserError
                        token = analyze(generator, analysis_type=name)
            elif token.type == "ID" and re.match("^A[CM]_", token.value):
                # 我们没有关注的AC, AM函数, 采用默认解析
                if




if __name__ == "__main__":
    filename = sys.argv[1]
    with open(filename) as fin:
        raw_data = fin.read()
    mylexer = M4Lexer()
    mylexer.build()

    generator = mylexer.get_token_iter(raw_data)

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
