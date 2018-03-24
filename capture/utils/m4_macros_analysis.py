# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: m4_macros_analysis.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-06 10:12:11
    @LastModif: 2018-03-06 20:12:02
    @Note:  Autotools function analysis module.
    This script can be use to analyze *.m4 and configure.ac files, and gains the export variables and conditions.
"""
from __future__ import absolute_import

import sys
import re
import types
import logging
import copy
import ply.lex as lex

if __name__ == "__main__":
    sys.path.append("../conf")
    import parse_logger
    parse_logger.addFileHandler("./capture.log", "capture")


logger = logging.getLogger("capture")

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


class M4Lexer(object):
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

    def t_COMMENT(self, t):
        r'\#.*|dnl.*'
        # pass    # ignore comment line
        return t

    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    def t_ID(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_]*'
        t.type = reserved.get(t.value, 'ID') # if in reserved, use own type, else use ID
        return t

    def t_error(self, t):
        logger.debug("Illegal character '%s', pos:(%d, %d)" % (t.value[0], t.lineno, t.lexpos))
        t.lexer.skip(1)

    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def clone(self):
        return self.lexer.clone()

    # Test it output
    def get_token_iter(self, data, lexer=None):
        if lexer is None:
            lexer = self.lexer

        lexer.input(data)
        last_token = lex.LexToken()
        last_token.type = ""
        last_token.value = ""
        last_token.lineno = -1
        last_token.lexpos = -1
        while True:
            tok = lexer.token()
            if not tok:
                break
            if tok.type == "COMMENT" and last_token.lineno != tok.lineno:
                # Pass comment line
                continue
            elif last_token.lineno == tok.lineno and \
                    last_token.lexpos + len(last_token.value) == tok.lexpos:
                # Only the #... are next to other part should be return
                #TODO: 需要重新分割这部分的 token 使得其能够作为
                pass
            elif tok.type != "COMMENT":
                pass
            else:
                continue

            last_token = tok
            yield tok


# TODO: 拓展表格，加入可能会出现的 IFELSE 宏定义函数，这种情况的话应该作为option来处理, 条件解析不出来就直接构建一个随机不重复的条件
# Analysis_type:
#     string: Means that we don't care about content, just concentrate on ']'
#     default: Using default method to analyze token flow.
#     call_function: Means that we will calling other function here.
#     ID_VAR & ID_VAR: Means the field content one ID. ID_VAR will export variable, ID_ENV will export condition.
#     func_name: Using to define a new m4 function
#     test: Using to define a test condition for a conditional variable export.
#     value: The default value for some variables define or export.
# The bool value represent whether this field is essential.
m4_macros_map = {
    "AC_DEFUN": ["func_name", True, "default", True],
    "AC_REQUIRE": ["call_function", True],
    "AC_MSG_CHECKING": ["string", True],
    "AC_MSG_RESULT": ["string", True],
    "AC_MSG_ERROR": ["string", True],
    "AC_SUBST": ["ID_VAR", True, "value", False],
    "AC_CONFIG_HEADERS": ["HEADERS", True],
    "AM_CONDITIONAL": ["ID_ENV", True, "test", False],
    "AC_MSG_WARN": ["string", True],
    "AC_HELP_STRING": ["string", True, "string", True],
    "AC_MSG_NOTICE": ["string", True],

    "AC_DEFINE_UNQUOTED": ["MACROS", True, "macros_value", True, "string", True],
    "AC_DEFINE": ["MACROS", True, "macros_value", True, "string", True],
}

left = ['LPAREN', 'LSPAREN', 'LBRACES',]
right = ['RPAREN', 'RSPAREN', 'RBRACES',]
filename_flags = ["-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]

# Temp data saving util
options = []
reverses = []
functions = {}
m4_libs = {}
config_h = {}
to_config = []
ac_headers = ""


has_macros = False


class ParserError(Exception):
    """Error happen in analyze configure.ac or *.m4 file"""
    def __init__(self, message=None):
        if message:
            self.args = (message,)
        else:
            self.args = ("Parser Error happen!",)


def check_next(generator, string):
    """Checking generator of the next value whether is same to string."""
    try:
        token = generator.next()
    except StopIteration:
        raise ParserError
    if token.type == string:
        return True
    raise ParserError


def try_next(generator, string):
    """
        Expect to gain string at generator next, if true, pass;
        or will seek back to last token place and return False
    """
    if not generator.has_next():
        return False
    token = generator.next()
    if token.type == string:
        return True
    generator.seek(generator.index - 1)
    return False


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


def _args_check_bool_expresion(generator, ends=["RPAREN", "RSPAREN"]):
    """Checking bool string like 'test ...' in args field of m4function."""
    option_list = []
    try:
        token = generator.next()
        if token.type != "test" and token.type != "LSPAREN":
            logger.debug("This is a nonstandard expression")
        option_list.append(token.value)

        quote_index = -1
        paren_count = 0
        while token.type not in ends or paren_count > 1:
            if token.type == "SEMICOLON":
                pass
            elif token.type == "DOUBLE_QUOTE":
                if quote_index < 0:
                    quote_index = len(option_list)
                else:
                    option_list[quote_index] = '"' + option_list[quote_index]
                    option_list[-1] += '"'
                    quote_index = -1
            elif token.type == "MINUS":
                if generator.index > 0:
                    last_token = generator.get_history(generator.index - 2)[0]
                    next_token = generator.next()
                    if last_token.type == "RSPAREN" or last_token.type == "test":
                        # It means this MINUS maybe use to represent argunments
                        option_list.append("-" + next_token.value)
                    else:
                        option_list[-1] += "-" + next_token.value
            elif token.type == "LPAREN":
                paren_count += 1
            elif token.type == "RPAREN":
                paren_count -= 1
            else:
                option_list.append(token.value)
            token = generator.next()
    except StopIteration:
        raise ParserError

    return " ".join(option_list)


def _check_bool_expresion(generator, ends=["then",]):
    """
        Checking bool string for 'if test ...' in if..else...
        TODO: There are still some problems for bool condition value return.
    """

    option_list = []
    try:
        token = generator.next()
        if token.type == "test":
            pass
        elif token.type == "LSPAREN":
            ends = ["RSPAREN",]
        else:
            logger.debug("This is a nonstandard expression")
        option_list.append(token.value)

        quote_index = -1
        quote_counts = 0
        while token.type not in ends and quote_counts >= 0:
            if token.type == "SEMICOLON":
                pass
            elif token.type == "DOUBLE_QUOTE":
                if quote_index < 0:
                    quote_index = len(option_list)
                elif quote_index < len(option_list):
                    option_list[quote_index] = '"' + option_list[quote_index]
                    option_list[-1] += '"'
                    quote_index = -1
                elif quote_index == len(option_list):
                    option_list.append('""')
                else:
                    raise ParserError
            elif token.type == "MINUS":
                if generator.index > 0:
                    last_token = generator.get_history(generator.index - 2)[0]
                    next_token = generator.next()
                    if last_token.type == "RSPAREN" or last_token.type == "test":
                        # It means this MINUS maybe use to represent argunments
                        option_list.append("-" + next_token.value)
                    else:
                        option_list[-1] += "-" + next_token.value
            elif token.type in left:
                quote_counts += 1
            elif token.type in right:
                quote_counts -= 1
            else:
                option_list.append(token.value)
            token = generator.next()
        if quote_counts < 0:
            generator.seek(generator.index - 1)
            return None
    except StopIteration:
        raise ParserError

    return " ".join(option_list)


def _check_sh_if(generator, level, func_name=None, allow_calling=False):
    """Checking 'if... else... ' and update options, and reverses status."""
    index = generator.index
    option = _check_bool_expresion(generator)
    if option is None:
        logger.debug("This if may be string line.")
        generator.seek(index)
        return False
    options.append(option)
    reverses.append(False)
    end_flags = False
    while not end_flags:
        analyze(generator, analysis_type="default", func_name=func_name,
                level=level + 1, ends=["else", "elif", "fi"], allow_calling=allow_calling)
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
    return True


def _check_sh_case(generator, level, func_name=None, allow_calling=False):
    """Checking 'case ...' and update options, and reverses status."""
    try:
        token = generator.next()
        token_list = []
        while token.type != "in":
            token_list.append(token.value)
            token = generator.next()
        var = "".join(token_list)

        end_flags = False
        token = generator.next()
        while not end_flags:
            token_list = []
            paren_count = 1
            while paren_count > 0:
                # or token.type != "RPAREN":
                token_list.append(token.value)
                token = generator.next()
                if token.type == "LPAREN":
                    paren_count += 1
                elif token.type == "RPAREN":
                    paren_count -= 1
            value = "".join(token_list)

            option = "{} = {}".format(var, value)
            options.append(option)
            reverses.append(False)
            analyze(generator, analysis_type="default", func_name=func_name, level=level + 1,
                    ends=["DOUBLE_SEMICOLON"], allow_calling=allow_calling)
            options.pop()
            reverses.pop()
            token = generator.next()

            if token.type == "esac":
                end_flags = True
        logger.debug("### End of case calling.")
    except StopIteration:
        raise ParserError


def _cache_check_assign(generator, var, lineno, type="="):
    """
        Assignment or appendage line analysis.
        TODO: Whether we need to save them and using to judge if...test...?
    """
    assignment_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*=\s*([^\s\)\]]*)")
    appendage_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*\+=\s*([^\s\)\]]*)")
    line = generator.get_line(lineno)
    index = line.find(var)
    var_line = line[index:]
    value = ""
    try:
        next_token = generator.next()
        quote_types = ["DOUBLE_QUOTE", "BACKQUOTE"]
        if next_token.type in quote_types:
            quote = next_token.value
            quote_type = next_token.type
            logger.debug("Expect quote: %s" % quote_type)
            last_token = next_token
            current_lineno = next_token.lineno
            next_token = generator.next()
            quotes_count = 0 if next_token.lineno != current_lineno else 1
            lines = [line,]
            while next_token.type != quote_type or last_token.type == "BACKSLASH":
                last_token = next_token
                next_token = generator.next()

                if next_token.lineno != current_lineno:
                    current_lineno = next_token.lineno
                    lines.append(generator.get_line(current_lineno))
                    quotes_count = 0

                if next_token.type == quote_type:
                    quotes_count += 1
            end_lineno = next_token.lineno
            end_line = generator.get_line(end_lineno)
            logger.debug("end line: %s" % end_line)
            logger.debug("end quote_count: %d" % quotes_count)
            end_index = 0
            while quotes_count > 0 and end_index != -1:
                end_index = end_line.find(quote, end_index)
                end_index += 1
                quotes_count -= 1
            logger.debug(lines)
            logger.debug("end_index: %d" % end_index)
            if end_index != -1:
                lines[-1] = lines[-1][:end_index]

            logger.debug("new lines: %s" % lines)
            # Remove comment part
            for i, line in enumerate(lines):
                comment_regex = re.compile(r'(.*)\s+(\#|dnl).*')
                comment_match = comment_regex.match(line)
                if comment_match:
                    lines[i] = comment_match.group(1)

            total_line = " ".join(lines)
            logger.debug("total line: %s" % total_line)
            # +1 is for double_quote or backquote
            start_index = index + len(var) + len(type) + 1
            logger.debug("start index: %d" % start_index)
            value = total_line[start_index:-1]
            logger.debug(value)

        elif lineno != next_token.lineno:
            generator.seek(generator.index - 1)
            value = ""
        else:
            assign_match = assignment_regex.match(var_line)
            append_match = appendage_regex.match(var_line)
            if assign_match or append_match:
                value = assign_match.group(2) if assign_match else append_match.group(2)

        return value
    except (StopIteration, ValueError, IndexError):
        raise ParserError


def _check_global_dict_empty(dict):
    """Checking whether the dict is empty and return default_N field to use."""
    default_n_regex = re.compile(r"default_\d+")
    default_N = 1
    for option_key in dict["option"].keys():
        if default_n_regex.match(option_key):
            default_N += 1
    if len(dict["defined"]) != 0 or len(dict["undefined"]) != 0 or len(dict["option"]) != 0:
        return True, default_N
    return False, 0


def _get_present_level_dict(start_dict, is_assign=False):
    """Get present option status dict in functions."""
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


def _check_next_empty_field(generator, empty_flags=["RSPAREN", "RPAREN", "COMMA"]):
    """Check next field whether is empty[in empty flags]"""
    token = generator.next()
    generator.seek(generator.index - 1)
    if token.type in empty_flags:
        return True
    return False


def macros_line_analyze(line, variables, generator, is_macros_line=False):
    """Analyzing macros line, and saving such variables to functions dict."""
    global has_macros
    macros_assignment_line_regex = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\"?([^\"]*)\"?")
    macros_appendage_line_regex = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\+=\s*\"?([^\"]*)\"?")
    # with_var_line_regex = re.compile(r"(.*)\$\(([a-zA-Z_][a-zA-Z0-9_]*)\)(.*)")

    with_quote_var = r'\$\([a-zA-Z_][a-zA-Z0-9_]*\)'
    without_quote_var = r'\$[a-zA-Z_][a-zA-Z0-9_]*'
    # var_pattern = with_quote_var + r"|" + without_quote_var
    with_var_line_pattern = r"(.*?)(" + with_quote_var + r")(.*)" + r"|" \
               + r"(.*?)(" + without_quote_var + r")(.*)"
    with_var_line_regex = re.compile(with_var_line_pattern)

    assign_match = macros_assignment_line_regex.match(line)
    append_match = macros_appendage_line_regex.match(line)
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
        if is_macros_line:
            variables[var]["has_macros"] = True

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

            if re.match("-D.*", word):
                has_macros = True
            with_var_line_match = with_var_line_regex.match(temp)
            slices = []
            while with_var_line_match:
                i = 1 if with_var_line_match.group(1) is not None else 4
                j = 2 if with_var_line_match.group(2) is not None else 5
                k = 3 if with_var_line_match.group(3) is not None else 6
                temp = with_var_line_match.group(i)
                undefine_var = with_var_line_match.group(j)
                other = with_var_line_match.group(k)
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
            if check_undefined(slices):
                if check_undefined_self(slices, var):
                    present_option_dict["is_replace"] = False
                    if len(slices) == 1:
                        temp = ""
                        continue
                present_option_dict["undefined"].append(transfer_word)
            else:
                present_option_dict["defined"].append(transfer_word)

            temp = ""
    return


def _check_ac_defunc(generator):
    """Checking AC_DEFUN field"""
    check_next(generator, "LPAREN")
    check_next(generator, "LSPAREN")
    token = generator.next()
    if token.type != "ID":
        raise ParserError
    func_name = token.value
    functions[func_name] = {
        "calling": [],
        "need_condition_var": [],
        "need_assign_var": [],
        "variables": {},
        "export_variables": {},
        "export_conditions": {}
    }
    check_next(generator, "RSPAREN")
    check_next(generator, "COMMA")
    analyze(generator, analysis_type="default", func_name=func_name, level=1)
    check_next(generator, "RPAREN")
    return


def _check_calling_args(generator, func_name, level, allow_calling=False):
    """Checking undefined function calling args."""
    analyze(generator, analysis_type="default", func_name=func_name, level=level + 1, allow_calling=allow_calling)
    generator.seek(generator.index - 1)
    last_token = generator.next()
    next_token = generator.next()
    logger.debug("print two: %s %s" % (last_token, next_token))
    # Some informal function format may be like:
    # FUNCTION([], []
    #           [], [])
    is_newline_seperate = (last_token.type == "RSPAREN" and
                           next_token.type != "RPAREN" and
                           next_token.type != "COMMA" and
                           last_token.lineno != next_token.lineno)
    while next_token.type == "COMMA" or is_newline_seperate:
        if not _check_next_empty_field(generator):
            analyze(generator, analysis_type="default", func_name=func_name,
                    level=level + 1, allow_calling=allow_calling)
        generator.seek(generator.index - 1)
        last_token = generator.next()
        next_token = generator.next()
        logger.debug("print two: %s %s" % (last_token, next_token))
        is_newline_seperate = (last_token.type == "RSPAREN" and
                               next_token.type != "RPAREN" and
                               next_token.type != "COMMA" and
                               last_token.lineno != next_token.lineno)
    logger.debug("End of function args analysis.")
    return next_token


def _calling_to_merge(func_name, funcname_tocall, *args):
    """
        Calling m4 macros and merge variables dict.

        TODO: args can be used to expend macros with arguments.
    """
    tocall_function = m4_libs.get(funcname_tocall, dict())
    present_function = functions.get(funcname_tocall, dict())
    if len(tocall_function) == 0 and len(present_function) == 0:
        logger.debug("{} may be a builtin function or loading fail.".format(funcname_tocall))
    elif len(present_function) != 0:
        tocall_function = present_function

    # Step 1: Merge variables for called function and calling function
    dest_variables = functions[func_name]["variables"]
    variables = tocall_function.get("variables", dict())
    for var in variables:
        if var not in dest_variables:
            variables[var] = {
                "defined": [],
                "undefined": [],
                "option": {},
                "is_replace": False
            }

        var_dict = variables[var]
        dest_var_dict = dest_variables[var]

        import queue
        option_queue = queue.Queue()

        (has_default, default_N) = _check_global_dict_empty(dest_var_dict)
        if has_default and var_dict.get("is_replace", False) and len(options) == 0:
            dest_var_dict[var][default_N] = {
                True: {
                    "defined": var_dict.get("defined", []),
                    "undefined": var_dict.get("undefined", []),
                    "option": {},
                    "is_replace": False
                },
                False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
            }
            for option in var_dict["option"]:
                if option not in dest_var_dict["option"]:
                    dest_var_dict["option"][option] = var_dict["option"][option]
                else:
                    option_queue.put((var_dict["option"][option][True], dest_var_dict["option"][option][True]))
                    option_queue.put((var_dict["option"][option][False], dest_var_dict["option"][option][False]))
        else:
            present_dest_dict = dest_var_dict
            for (option, reverse) in zip(options, reverses):
                if option not in dest_var_dict["option"]:
                    present_dest_dict["option"][option] = {
                        True: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                        False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                    }
                present_dest_dict = present_dest_dict["option"][option][not reverse]

            option_queue.put((var_dict, present_dest_dict))

        while not option_queue.empty():
            try:
                (src, dest) = option_queue.get(timeout=0.1)
            except queue.Empty:
                break

            if src.get("is_replace", False):
                dest["defined"] = src.get("defined", [])
                dest["undefined"] = src.get("undefined", [])
            else:
                dest["defined"].extend(src.get("defined", []))
                dest["undefined"].extend(src.get("undefined", []))

            for option in src["option"]:
                if option not in dest["option"]:
                    dest["option"][option] = src["option"][option]
                else:
                    option_queue.put((src["option"][option][True], dest["option"][option][True]))
                    option_queue.put((src["option"][option][False], dest["option"][option][False]))

    # Step 2: Merge export variables
    export_vars_dict = tocall_function.get("export_variables", dict())
    for export_var in export_vars_dict:
        if "export_variables" not in functions[func_name]:
            functions[func_name]["export_variables"] = dict()

        if export_var not in functions[func_name]["export_variables"]:
            functions[func_name]["export_variables"][export_var] = None

    # Step 3: Merge export conditions
    export_condition_dict = tocall_function.get("export_conditions", dict())
    for export_condition in export_condition_dict:
        if "export_conditions" not in functions[func_name]:
            functions[func_name]["export_conditions"] = dict()

        if export_condition not in functions[func_name]["export_conditions"]:
            functions[func_name]["export_conditions"][export_condition] = None
    return True


def analyze(generator, analysis_type="default", func_name=None, level=0,
            ends=["RSPAREN",], allow_defunc=False, allow_calling=False):
    """
    The main recursion function for configure.ac and *.m4 file analysis.
    :param generator:                   A CacheGenerator instance for iteratively getting token.
                                        When generator has no next token, will raise a StopIteration Exception.
    :param analysis_type:               Analysis_type will define which more we choose to checking fields.
    :param func_name:                   The present func_name, this will help to saving variables and conditions.
    :param level:                       The present recursion level.
    :param ends:                        The end flags for this calling recursion.
    :param allow_defunc:                Whether allow to recognize AC_DEFUN.
                                        This may be used in configure.ac top level checking, which is allow to define
                                        m4 function here.
                                        But when our recursion walk into other function field or if...else... or case,
                                        this arg will be set to False
    :return:
    """
    if func_name is None:
        logger.debug("Functions can't be None type.")
        return

    logger.debug("# calling analysis with type: " + analysis_type +
                " In function: " + func_name + "\tlevel:" + str(level))
    global has_macros
    quote_count = 0
    roll_back_times = 0
    try:
        start_tokens = [generator.next() for _ in range(2)]
    except StopIteration:
        raise ParserError
    if start_tokens[0].type == "LSPAREN" and start_tokens[1].type == "LSPAREN":
        # Double quote include data is code for c/c++ which is used to automatically generate new source file.
        # Because we don't care about them, we skip them here.
        quote_count += 2
        token = None
        while quote_count != 0:
            token = generator.next()
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1
        if token and token.type == "RSPAREN":
            return
        else:
            raise ParserError
    elif start_tokens[0].type != "LSPAREN" and len(ends) == 1 and ends[0] == "RSPAREN":
        # For such informal case, the end flags need to change to COMMA or RPAREN
        roll_back_times += 1
        ends = ["COMMA", "RPAREN"]
        logger.debug("Set ends: %s" % ends)

    if start_tokens[0].type == "LSPAREN":
        generator.seek(generator.index - 1)
        quote_count += 1
        token = generator.next()
    else:
        generator.seek(generator.index - 2)
        token = generator.next()

    if analysis_type == "default":
        # Count of quotes, if quote_count == 0, it means the process main back to last recursion
        # if quote_count <= 1 and token in ends:
        #     logger.debug("Maybe empty analysis fields.")

        while quote_count > 0 or token.type not in ends:
            # 1. Analyze some defined function from m4_macros_map
            if token.type == "ID" and token.value in m4_macros_map:
                funcname_tocall = token.value
                logger.debug("## Start defined function analysis\tname: " + funcname_tocall)
                if token.value == "AC_DEFUN":
                    if allow_defunc:
                        logger.debug("## Start defining a functions.")
                        _check_ac_defunc(generator)
                    else:
                        raise ParserError

                check_next(generator, "LPAREN")
                for i in range(len(m4_macros_map[token.value]) // 2):
                    name = m4_macros_map[token.value][i * 2]
                    is_essential = m4_macros_map[token.value][i * 2 + 1]

                    if is_essential:
                        if i != 0:
                            check_next(generator, "COMMA")
                        analyze(generator, analysis_type=name, func_name=func_name,
                                level=level + 1, allow_calling=allow_calling)
                    else:
                        try:
                            next_token = generator.next()
                            if next_token.type == "COMMA":
                                if not _check_next_empty_field(generator):
                                    analyze(generator, analysis_type=name, func_name=func_name,
                                            level=level + 1, allow_calling=allow_calling)
                            else:
                                if name == "value" and len(functions[func_name]["need_assign_var"]) != 0:
                                    # Need to remove waiting default value variable.
                                    functions[func_name]["need_assign_var"].pop()
                                generator.seek(generator.index - 1)
                            logger.debug("defined next_token: %s" % next_token)

                        except StopIteration:
                            raise ParserError

                check_next(generator, "RPAREN")
                token = generator.next()
                if allow_calling:
                    _calling_to_merge(func_name, funcname_tocall)

            elif token.type == "ID" and re.match("^A[CM]_", token.value):
                # 2. Analyze some undefined functions started with AC | AM.
                #   Using "default" mode.
                funcname_tocall = token.value
                logger.debug("## Start undefined function analysis\tname: " + funcname_tocall)

                try:
                    next_token = generator.next()
                    # functions[func_name]["calling"].append(token.value)
                    # logger.critical(next_token)
                    if next_token.type != "LPAREN":
                        # Maybe the MACROS function without args.
                        logger.debug(quote_count)
                        token = next_token
                        if token.type in ends and quote_count <= 1:
                            break
                        else:
                            continue
                    next_token = _check_calling_args(generator, func_name, level, allow_calling=allow_calling)
                except StopIteration:
                    raise ParserError

                if next_token.type != "RPAREN":
                    raise ParserError
                token = generator.next()
                if allow_calling:
                    _calling_to_merge(func_name, funcname_tocall)

            elif token.type == "ID":
                # 3. Analyze some assignment line, and skip some line we don't care.
                logger.debug("## Start unknown line analysis %s" % token)
                var = token.value
                lineno = token.lineno
                try:
                    next_token = generator.next()
                    if next_token.type == "ASSIGN" or next_token.type == "APPEND":
                        is_assign = True if next_token.type == "ASSIGN" else False
                        value = _cache_check_assign(generator, var, lineno, next_token.value)
                        if value is not None:
                            # TODO: The assignment line actually should be saved.
                            logger.debug("ASSIGN value: %s=%s" % (var, value))
                            line = var + "=" + value
                            variables = functions[func_name]["variables"]
                            macros_line_analyze(line, variables, generator)
                        token = generator.next()

                    elif next_token.type == "LPAREN":
                        funcname_tocall = var
                        logger.debug("## Start checking user defined function. name: %s" % funcname_tocall)
                        # functions[func_name]["calling"].append(token.value)
                        # logger.critical(next_token)
                        if next_token.type != "LPAREN":
                            # Maybe the MACROS function without args.
                            logger.debug(quote_count)
                            token = next_token
                            if token.type in ends and quote_count <= 1:
                                break
                            else:
                                continue
                        next_token = _check_calling_args(generator, func_name, level, allow_calling=allow_calling)
                        if next_token.type != "RPAREN":
                            raise ParserError
                        token = generator.next()
                        if allow_calling:
                            _calling_to_merge(func_name, funcname_tocall)

                    else:
                        lineno = token.lineno
                        if token.type == "ID" and next_token.type in ends:
                            # Directly break
                            token = next_token
                            break
                        # When start a new line, we should end up this loop.
                        one_word_line = True
                        sub_quotes_count = 0
                        logger.debug("quote count: %d" % sub_quotes_count)
                        while (token.type not in ends or sub_quotes_count > 0) and \
                                token.lineno == lineno:
                            one_word_line = False
                            if next_token.type in left:
                                quote_count += 1
                            if next_token.type in right:
                                quote_count -= 1
                            token = next_token
                            next_token = generator.next()
                        logger.debug("quote count: %d" % sub_quotes_count)
                        logger.debug("Move outer token:%s" % token)
                        if not one_word_line:
                            generator.seek(generator.index - 2)
                            token = generator.next()
                except StopIteration:
                    raise ParserError

            elif token.type == "MACROS":
                # 4. Analyze Macros assignment line.
                logger.debug("## Start Macros line analysis %s" % token)
                line = token.value
                variables = functions[func_name]["variables"]
                has_macros = True

                macros_line_analyze(line, variables, generator, is_macros_line=True)
                token = generator.next()

            elif token.type == "if":
                logger.debug("## Start if analysis.")
                status = _check_sh_if(generator, level, func_name=func_name, allow_calling=allow_calling)
                if status:
                    token = generator.next()
                else:
                    token.type = "ID"
                    logger.debug("## End of if analysis fail. Try string analysis.")
                    continue
                logger.debug("## End of if analysis pass.")

            elif token.type == "case":
                logger.debug("## Start case analysis.")
                _check_sh_case(generator, level, func_name=func_name, allow_calling=allow_calling)
                token = generator.next()
                logger.debug("## End of case analysis.")

            elif token.type in left:
                quote_count += 1
                token = generator.next()
            elif token.type in right:
                quote_count -= 1
                if quote_count == 0 and token.type in ends:
                    break
                token = generator.next()

            else:
                # 4. Start with some undefined token, we maybe skip it.
                token = generator.next()

            if token.type in ends and quote_count <= 1:
                break

    elif analysis_type == "value":
        logger.debug("## Start value analysis.")
        value = []
        quote_count = 0
        while token.type not in ["RSPAREN", "RPAREN", "COMMA"] or quote_count != 0:
            value.append(token.value)
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1

            try:
                token = generator.next()
            except StopIteration:
                raise ParserError

        # TODO: Need to check option
        need_assign_vars = functions[func_name]["need_assign_var"]
        export_vars = functions[func_name]["export_variables"]
        if len(need_assign_vars) != 0:
            var = need_assign_vars.pop()
            var_dict = export_vars[var]
            var_dict["defined"] = " ".join(value)

    elif analysis_type == "string":
        logger.debug("## Start string analysis.")
        value = []
        quote_count = 0
        while token.type not in ["RSPAREN", "RPAREN"] or quote_count != 0:
            value.append(token.value)
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1

            try:
                token = generator.next()
            except StopIteration:
                raise ParserError

        global to_config
        logger.debug(to_config)
        if len(to_config) == 2:
            macros_name = to_config[0]
            config_h[macros_name] = {
                "value": to_config[1],
                "description": " ".join(value),
                "option": copy.deepcopy(options),
                "reverse": copy.deepcopy(reverses)
            }
            to_config.clear()

    elif analysis_type == "test":
        logger.debug("## Start test analysis")
        generator.seek(generator.index - 1)
        bool_str = _args_check_bool_expresion(generator)
        export_conditions = functions[func_name]["export_conditions"]
        if len(functions[func_name]["need_condition_var"]) != 0:
            condition_var = functions[func_name]["need_condition_var"].pop()
            export_conditions[condition_var] = bool_str
            generator.seek(generator.index - 1)
            token = generator.next()
        else:
            raise ParserError

    elif analysis_type == "call_function":
        if token.type == "ID":
            functions[func_name]["calling"].append(token.value)
        else:
            raise ParserError
        token = generator.next()

    elif analysis_type == "ID_ENV":
        logger.debug("## Start ID_ENV analysis")
        export_conditions = functions[func_name]["export_conditions"]
        export_conditions[token.value] = None
        functions[func_name]["need_condition_var"].append(token.value)
        token = generator.next()

    elif analysis_type == "ID_VAR":
        export_vars = functions[func_name]["export_variables"]
        export_vars[token.value] = {
            "defined": [],
            "undefined": [],
            "option": {},
            "is_replace": True
        }
        functions[func_name]["need_assign_var"].append(token.value)
        token = generator.next()

    elif analysis_type == "macros_value":
        value = []
        quote_count = 0
        while token.type not in ["RSPAREN", "RPAREN", "COMMA"] or quote_count != 0:
            value.append(token.value)
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1

            try:
                token = generator.next()
            except StopIteration:
                raise ParserError

        str_value = " ".join(value)
        if re.search("\$", str_value):
            to_config.append("")
        else:
            to_config.append(str_value)

    elif analysis_type == "MACROS":
        macros_name = token.value
        logger.debug("## Start MACROS analysis, macros name: %s" % macros_name)
        to_config.clear()
        try:
            token = generator.next()
            if token.type in ["RSPAREN", "COMMA"]:
                to_config.append(macros_name)
            else:
                quote_count = 0
                while token.type not in ["RSPAREN", "COMMA"] or quote_count != 0:
                    if token.type in left:
                        quote_count += 1
                    elif token.type in right:
                        quote_count -= 1
                    token = generator.next()
        except StopIteration:
            raise ParserError

    elif analysis_type == "HEADERS":
        value = []
        global ac_headers
        quote_count = 0
        while token.type not in ["RSPAREN", "RPAREN"] or quote_count != 0:
            value.append(token.value)
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1

            try:
                token = generator.next()
            except StopIteration:
                raise ParserError
        str_value = "".join(value)
        ac_headers = str_value

    if token.type in ends:
        [generator.seek(generator.index - 1) for _ in range(roll_back_times)]
        logger.debug("### END CALLING: %s" % token)
        return
    else:
        raise ParserError


def functions_analyze(generator, filename):
    # This function will analyze token flow and concentrates on AC_DEFUN
    logger.info("checking m4 file: %s" % filename)
    global functions
    global has_macros
    global options
    global reverses
    options = []
    reverses = []
    has_macros = False
    temp_functions = copy.deepcopy(functions)
    try:
        if "other" not in functions:
            functions["other"] = {
                "variables": {}
            }
        while generator.has_next():
            token = generator.next()
            if token.type == "ID" and token.value == "AC_DEFUN":
                try:
                    _check_ac_defunc(generator)
                except ParserError:
                    logger.warning("Analyze AC FUNCTION fail. Skip the left part.")
                    while token.value != "AC_DEFUN":
                        token = generator.next()
                    generator.seek(generator.index - 1)
            else:
                while token.value != "AC_DEFUN":
                    token = generator.next()
                    if token.type == "MACROS":
                        variables = functions["other"]["variables"]
                        line = token.value
                        macros_line_analyze(line, variables, generator)
                generator.seek(generator.index - 1)
    except StopIteration:
        logger.warning("File AC_DEFUN analyze complete.")

    if not has_macros:
        functions = temp_functions

    return functions


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
        Note: We can add more features like getting same feature cluster.
    """

    def __init__(self, generator, origin_data=None):
        self._max_index = 0
        self._index = 0
        self._caches = []
        self._has_next = True

        if not isinstance(generator, types.GeneratorType):
            raise TypeError
        self._generator = generator

        try:
            data = next(self._generator)
            self._caches.append(data)
            self._index += 1
            self._set_max()
        except StopIteration:
            self._has_next = False

        if origin_data:
            self._origin_data = origin_data
            self._origin_lines = origin_data.split("\n")

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
        return data

    def last(self):
        if self._index != 0:
            self._index -= 1
            data = self._caches[self._index]
            return data
        return None

    def get_history(self, start_index=0):
        return self._caches[start_index - 1:-1] if start_index else self._caches[start_index:-1]

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

    def get_line(self, lineno, end=None):
        if self._origin_lines is None:
            raise ValueError("No origin data.")

        if end is None or not isinstance(end, int):
            if 0 <= lineno < len(self._origin_lines):
                return self._origin_lines[lineno - 1]
            else:
                raise IndexError
        elif lineno >= end:
            raise ValueError("lineno < end is required.")
        else:
            if 0 <= lineno < len(self._origin_lines) and 0 < end < len(self._origin_lines):
                return self._origin_lines[lineno, end]


if __name__ == "__main__":
    mylexer = M4Lexer()
    mylexer.build()
    for i, filename in enumerate(sys.argv[1:]):

        with open(filename) as fin:
            raw_data = fin.read()
        # logger.debug(raw_data)
        generator = mylexer.get_token_iter(raw_data)

        cache_generator = CacheGenerator(generator, origin_data=raw_data)
        functions_analyze(cache_generator, filename)
        import json

        with open("./data_func%d.out"%i, "w") as fout:
            json.dump(functions, fout, indent=4)

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
