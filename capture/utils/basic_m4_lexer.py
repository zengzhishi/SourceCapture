# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: basic_m4_lexer.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-26 20:32:37
    @LastModif: 2018-03-26 20:32:37
    @Note:
"""

import ply.lex as lex


reserved = {
    "if": "if",
    "else": "else",
    "elif": "elif",
    "test": "test",
    "then": "then",
    "fi": "fi",
    "case": "case",
    "in": "in",
    "esac": "esac",
}

# C MACROS line will let some right RSPAREN and RPAREN token be recognized as comment line.
# So we need to recognize them out, and skip them.
c_include_lquote = r'["<]'
c_include_rquote = r'[">]'
c_include_name = r'[a-zA-Z_][a-zA-Z0-9_/.]*'
c_macros = r'\#[\t ]*include\s+' + c_include_lquote + c_include_name + c_include_rquote + \
           r'|' + r'\#[\t ]*ifdef[^\n]*' + \
           r'|' + r'\#[\t ]*else' + \
           r'|' + r'\#[\t ]*if[^\n]*' + \
           r'|' + r'\#[\t ]*endif' + \
           r'|' + r'\#[\t ]*define[\t ]+[a-zA-Z_][a-zA-Z0-9_]*[\t ]+[^\s]*'


class NoCommentLexer(object):
    # List of token names.
    tokens = [
                 "MACROS",
                 "VAR",
                 "FUNC_ARG",

                 "QUE_MARK",
                 'COLON',
                 'DOUBLE_SEMICOLON',         # for case seperating
                 'SEMICOLON',
                 'C_MACROS',
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

                 'GREATER_OR_EQUAL',
                 'LESS_OR_EQUAL',

                 'GREATER',
                 'LESS',

                 'EQUAL',
                 'ASSIGN',
                 'APPEND',
                 'CASE_OR',
                 'MINUS',
                 'PLUS',
                 'AND',
                 'OR',
                 'NOT',
                 'CARET',
                 'HOME',
                 'PERCENT',

                 'BACKQUOTE',
                 'AT',
                 'DOLLAR',
                 'AMPERSAND',
                 'SLASH',
                 'BACKSLASH',
                 'NUMBER',
                 'ID',
             ] + list(reserved.values())

    t_VAR = r'\$[a-zA-Z_][a-zA-Z0-9_]*|\$\([a-zA-Z_][a-zA-Z0-9_]*\)'
    t_FUNC_ARG = r'\$\d+|\$\(\d+\)'
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

    t_GREATER_OR_EQUAL = r'\>\='
    t_LESS_OR_EQUAL = r'<='
    t_GREATER = r'>'
    t_LESS = r'<'
    t_EQUAL = r'\=\='
    t_APPEND = r'\+\='
    t_ASSIGN = r'\='
    t_PLUS = r'\+'
    t_NOT = r'!'
    t_CARET = r'\^'
    t_HOME = r'\~'
    t_PERCENT = r'\%'

    t_BACKQUOTE = r'`'
    t_AT = r'@'
    t_DOLLAR = r'\$'
    t_AMPERSAND = r'\&'
    t_SLASH = r'\/'
    t_BACKSLASH = r'\\'
    t_NUMBER = r'\d+\.?\d*'

    t_ignore = ' \t'

    def t_MACROS(self, t):
        r'.*\=.*\-D\$?\(?[a-zA-Z_][a-zA-Z0-9_].*'
        # print("macros line: {}".format(t.value))
        return t

    @lex.TOKEN(c_macros)
    def t_C_MACROS(self, t):
        return t

    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    def t_ID(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_]*'
        t.type = reserved.get(t.value, 'ID') # if in reserved, use own type, else use ID
        return t

    def t_error(self, t):
        t.lexer.skip(1)

    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def t_COMMENT(self, t):
        r'dnl.*'
        pass

    def get_token_iter(self, data, lexer=None):
        if lexer is None:
            lexer = self.lexer
        self.lexer.input(data)
        while True:
            tok = lexer.token()
            if not tok:
                break
            yield tok

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
