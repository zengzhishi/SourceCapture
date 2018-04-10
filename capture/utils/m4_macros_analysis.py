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
import capture.utils.basic_m4_lexer as basic_m4_lexer
import capture.utils.capture_util as capture_util
from capture.utils.capture_util import ParserError

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
    "for": "for",
    "do": "do",
    "done": "done",
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
            elif tok.type == "COMMENT" and last_token.lineno == tok.lineno and \
                    last_token.lexpos + len(last_token.value) == tok.lexpos:
                # Only the #... are next to other part should be return
                #TODO: 需要重新分割这部分的 token 使得其能够作为
                nocoment_lexer = basic_m4_lexer.NoCommentLexer()
                nocoment_lexer.build()
                for token in nocoment_lexer.get_token_iter(tok.value):
                    token.lineno += tok.lineno - 1
                    token.lexpos += tok.lexpos
                    yield token
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
    # "AS_HELP_STRING": ["string", True, "string", True],
    "AC_MSG_NOTICE": ["string", True],
    "AC_LINK_IFELSE": ["string", True, "default", True, "default", False],

    "AC_DEFINE_UNQUOTED": ["MACROS", True, "macros_value", False, "string", False],
    "AC_DEFINE": ["MACROS", True, "macros_value", False, "string", False],
}

left = ['LPAREN', 'LSPAREN', 'LBRACES',]
right = ['RPAREN', 'RSPAREN', 'RBRACES',]
filename_flags = ["-I", "-isystem", "-iquote", "-include", "-imacros", "-isysroot"]

has_macros = False


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
        raise

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
        logger.warning("This may not be a formal shell if else string.")
        raise

    return " ".join(option_list)


def _cache_check_assign(generator, var, lineno, type="=", ends=None):
    """
        Assignment or appendage line analysis.
        TODO: Whether we need to save them and using to judge if...test...?
    """
    if ends is None:
        ends = ["RPAREN", "COMMA"]
    assignment_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*=\s*([^\s\)\]]*)")
    appendage_regex = re.compile(r"([a-zA-Z_]+[a-zA-Z0-9_]*)\s*\+=\s*([^\s\)\]]*)")
    line = generator.get_line(lineno)
    index = line.find(var)
    var_line = line[index:]
    value = ""
    try:
        next_token = generator.next()
        # An empty assignment line without change lines
        if next_token.type in ends:
            generator.seek(generator.index - 1)
            return ""

        quote_types = ["DOUBLE_QUOTE", "BACKQUOTE", "QUOTE"]
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
        logger.warning("Assignment line analysis fail, return empty value.")
        return ""


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


def _get_present_level_dict(start_dict, options, reverses, is_assign=False):
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


def macros_line_analyze(line, variables, generator, options, reverses, is_macros_line=False):
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

        present_option_dict = _get_present_level_dict(variables[var], options, reverses,
                                                      True if assign_match else False)
        present_option_dict["is_replace"] = True if assign_match else False
        present_option_dict["defined"] = present_option_dict["defined"] if append_match else []
        present_option_dict["undefined"] = present_option_dict["undefined"] if append_match else []

        words = capture_util.split_line(value)
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


def get_fields(generator, is_string=False):
    """
    Get fields from generator, the field end flags will be influenced by several value, like
        1. whether is under quote or double quote
        2. whether is under any types of parens.
    :param generator:   CacheGenerator to query value from lex token generator.
    :return:
    """
    sparen_count = 0
    quote_count = 0
    in_quote = False
    in_double_quote = False
    in_case_count = 0
    case_quote_list = []
    try:
        token = generator.next()
        fields_tokens = list()
        # Empty field
        if token.type in ("COMMA", "RPAREN"):
            generator.seek(generator.index - 1)
            return fields_tokens, is_string

        if is_string:
            ends = ["COMMA", "RPAREN"]
            while token.type not in ends or quote_count > 0:
                fields_tokens.append(token)
                if token.type in left:
                    quote_count += 1
                elif token.type in right:
                    quote_count -= 1
                token = generator.next()
            generator.seek(generator.index - 1)
        else:
            # field start with '['
            if token.type == "LSPAREN":
                fields_tokens.append(token)
                # Left the first SPAREN
                while token.type == "LSPAREN":
                    sparen_count += 1
                    token = generator.next()

                if sparen_count > 1:
                    # May be insert some c/c++ code here.
                    generator.seek(generator.index - sparen_count)
                    return get_fields(generator, is_string=True)

                while sparen_count != 0:
                    # Under string flags, in '...' or "..."

                    if in_quote:
                        if token.type == "QUOTE" and fields_tokens[-1].type != "BACKSLASH":
                            in_quote = False
                        fields_tokens.append(token)
                    elif in_double_quote:
                        if token.type == "DOUBLE_QUOTE" and fields_tokens[-1].type != "BACKSLASH":
                            in_double_quote = False
                        fields_tokens.append(token)
                    # Go into string analysis.
                    elif token.type == "QUOTE":
                        in_quote = True
                        fields_tokens.append(token)
                    elif token.type == "DOUBLE_QUOTE":
                        in_double_quote = True
                        fields_tokens.append(token)
                    elif token.type == "case":
                        in_case_count += 1
                        case_quote_list.append(quote_count)
                        fields_tokens.append(token)
                    elif token.type == "esac":
                        if len(case_quote_list) != 0:
                            quote_count = case_quote_list.pop()
                        in_case_count -= 1
                        fields_tokens.append(token)
                    # For the outer RSPAREN, will not save it.
                    elif quote_count == 0 and in_case_count == 0 and token.type == "RSPAREN":
                        sparen_count -= 1
                        if sparen_count == 0:
                            fields_tokens.append(token)

                    elif token.type in left:
                        quote_count += 1
                        fields_tokens.append(token)
                    elif token.type in right:
                        quote_count -= 1
                        fields_tokens.append(token)
                    else:
                        fields_tokens.append(token)
                    token = generator.next()

                generator.seek(generator.index - 1)
                if token.type not in ("COMMA", "RPAREN"):
                    # The command fields has multi command, but without SPAREN to include them
                    sub_fields, status = get_fields(generator)
                    is_string = is_string and status
                    fields_tokens.extend(sub_fields)
            # Field not start with "[", the end flags are "," and ")"
            # But we still need to concerned about the influence of quotes and parens.
            else:
                while quote_count > 0 or in_quote or in_double_quote \
                        or in_case_count != 0 or token.type not in ("COMMA", "RPAREN"):
                    if in_quote:
                        if token.type == "QUOTE" and fields_tokens[-1].type != "BACKSLASH":
                            in_quote = False
                        fields_tokens.append(token)
                    elif in_double_quote:
                        if token.type == "DOUBLE_QUOTE" and fields_tokens[-1].type != "BACKSLASH":
                            in_double_quote = False
                        fields_tokens.append(token)
                    # Go into string analysis.
                    elif token.type == "QUOTE":
                        in_quote = True
                        fields_tokens.append(token)
                    elif token.type == "DOUBLE_QUOTE":
                        in_double_quote = True
                        fields_tokens.append(token)
                    elif token.type == "case":
                        in_case_count += 1
                        fields_tokens.append(token)
                    elif token.type == "esac":
                        in_case_count -= 1
                        fields_tokens.append(token)
                    elif token.type in left:
                        quote_count += 1
                        fields_tokens.append(token)
                    elif token.type in right:
                        quote_count -= 1
                        fields_tokens.append(token)
                    else:
                        fields_tokens.append(token)
                    token = generator.next()

                generator.seek(generator.index - 1)

        return fields_tokens, is_string
    except StopIteration:
        if sparen_count != 0 or quote_count != 0 or in_quote or in_double_quote:
            raise ParserError


def fields_split(generator, field_defined=None):
    """
    Split the one command arguments line into a list of fields.
    :param generator:
    :return:
    """
    if not isinstance(field_defined, list):
        field_defined = list()
    args_fields = []
    analysis_types = []
    token = generator.next()
    # With args
    if token.type == "LPAREN":
        i = 0
        while token.type != "RPAREN":
            is_string = False
            if 2 * i < len(field_defined):
                analysis_type = field_defined[2 * i]
                if analysis_type in ("value", "string", "ID_ENV", "ID_VAR", "call_function"):
                    is_string = True
            else:
                analysis_type = "default"

            field, is_string = get_fields(generator, is_string)
            args_fields.append(field)
            analysis_types.append("string" if is_string else analysis_type)
            token = generator.next()
            i += 1
    return args_fields, analysis_types


def get_temp_generator(fields, generator):
    origin_raw_data = generator.origin_data

    def iter(list):
        for item in list:
            yield item

    return CacheGenerator(iter(fields), origin_raw_data)


class M4Analyzer(object):
    options = list()
    reverses = list()
    functions = dict()
    m4_libs = dict()
    config_h = dict()
    to_config = list()
    ac_headers = ""

    def __init__(self):
        pass

    def __del__(self):
        pass

    def functions_analyze(self, generator, filename):
        # This function will analyze token flow and concentrates on AC_DEFUN
        logger.info("checking m4 file: %s" % filename)
        try:
            if "other" not in self.functions:
                self.functions["other"] = {
                    "variables": {}
                }
            others = self.functions.get("other", dict())
            while generator.has_next():
                token = generator.next()
                if token.type == "ID" and token.value == "AC_DEFUN":
                    try:
                        self._check_ac_defunc(generator)
                    except ParserError:
                        logger.debug("Analyze AC FUNCTION fail. Skip the left part.")
                        while token.value != "AC_DEFUN":
                            token = generator.next()
                        generator.seek(generator.index - 1)
                else:
                    while token.value != "AC_DEFUN":
                        token = generator.next()
                        if token.type == "MACROS":
                            variables = others.get("variables", dict())
                            line = token.value
                            macros_line_analyze(line, variables, generator, self.options, self.reverses)
                    generator.seek(generator.index - 1)
        except StopIteration:
            logger.debug("File:%s AC_DEFUN analyze complete." % filename)
            return True
        except:
            logger.error("File:%s AC_DEFUN analyze fail." % filename)
            return False

    def command_analyze(self, generator, analysis_type="default", func_name=None, level=0,
                        ends=None, allow_defunc=False, allow_calling=False):

        logger.debug("# calling analysis with type: " + analysis_type +
                     " In function: " + func_name + "\tlevel:" + str(level))
        if func_name is None:
            logger.debug("Functions can't be None type.")
            return

        if func_name not in self.functions:
            self.functions[func_name] = {
                "calling": [],
                "need_condition_var": [],
                "need_assign_var": [],
                "variables": {},
                "export_variables": {},
                "export_conditions": {}
            }

        dest_functions = self.functions.get(func_name, dict())
        export_conditions = dest_functions.get("export_conditions", dict())
        export_vars = dest_functions.get("export_variables", dict())
        need_assign_vars = dest_functions.get("need_assign_var", list())
        need_condition_var = dest_functions.get("need_condition_var", list())
        try:
            if analysis_type == "default":
                self._default_analyze(generator, func_name, level + 1, ends=ends,
                                      allow_defunc=allow_defunc,
                                      allow_calling=allow_calling)

            elif analysis_type == "value":
                value = self._value_analyze(generator)
                if len(need_assign_vars) != 0:
                    var = need_assign_vars.pop()
                    var_dict = export_vars.get(var, dict())
                    var_dict["defined"] = value

            elif analysis_type == "string":
                return self._string_analyze(generator)

            elif analysis_type == "test":
                generator.seek(generator.index - 1)
                bool_str = _args_check_bool_expresion(generator)
                if len(need_assign_vars) != 0:
                    condition_var = need_assign_vars.pop()
                    export_conditions[condition_var] = bool_str
                    generator.seek(generator.index - 1)
                else:
                    raise ParserError

            elif analysis_type == "call_function":
                token = generator.next()
                if token.type != "ID":
                    raise ParserError
                name = token.value
                self._calling_to_merge(func_name, name)

            elif analysis_type == "ID_ENV":
                token = generator.next()
                # TODO: Concern whether we need to add option condition.
                export_conditions[token.value] = {
                    "defined": [], "undefined": [], "option": {}, "is_replace": True
                }
                need_condition_var.append(token.value)
                return

            elif analysis_type == "ID_VAR":
                token = generator.next()
                export_vars[token.value] = {
                    "defined": [],
                    "undefined": [],
                    "option": {},
                    "is_replace": True
                }
                need_assign_vars.append(token.value)
                return

            elif analysis_type == "HEADERS":
                self._headers_analyze(generator)

            else:
                logger.critical("Unknown analysis_type.")
                return

        except StopIteration:
            logger.debug("No next token, stop command analysis.")

    def configure_ac_analyze(self, generator, analysis_type="default", level=0):
        if len(self.functions) != 0:
            self.m4_libs = self.functions
            self.functions = dict()

        func_name = "configure_ac"
        self.functions[func_name] = {
            "calling": [],
            "need_condition_var": [],
            "need_assign_var": [],
            "variables": {},
            "export_variables": {},
            "export_conditions": {}
        }

        try:
            self.command_analyze(generator, analysis_type=analysis_type, func_name=func_name,
                                 level=level, allow_defunc=True, allow_calling=True)
        except StopIteration:
            logger.debug("Complete configure_ac command analysis.")
        except:
            logger.debug("Error happen in configure_ac command analysis.")
            return False
        return True

    def _headers_analyze(self, generator):
        value = []
        quote_count = 0
        token = generator.next()
        while token.type not in ["RSPAREN", "RPAREN"] or quote_count != 0:
            value.append(token.value)
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1

            try:
                token = generator.next()
            except StopIteration:
                break
        str_value = "".join(value)
        self.ac_headers = str_value

    def _default_analyze(self, generator, func_name, level=0, ends=None,
                              allow_defunc=False, allow_calling=False):
        if func_name is None:
            logger.debug("Functions can't be None type.")
            return
        if ends is None:
            ends = ["RPAREN", "COMMA"]
        dest_functions = self.functions.get(func_name, dict())

        token = generator.next()
        paren_count = 0
        in_double_quote = False
        in_quote = False
        while paren_count != 0 or in_double_quote or in_quote or token.type not in ends:
            if token.type == "ID":
                logger.debug("## Start unknown line analysis, start with: %s" % token)
                lineno = token.lineno
                var = token.value
                if var in m4_macros_map:
                    # Defined function analysis
                    self._defined_macros_analyze(generator, var, func_name, level + 1,
                                                 allow_defunc=allow_defunc, allow_calling=allow_calling)
                next_token = generator.next()
                if next_token.type == "LPAREN":
                    # Undefined function analysis
                    generator.seek(generator.index - 1)
                    self._undefined_macros_analyze(generator, var, func_name, level + 1,
                                                   allow_calling=allow_calling)
                    token = generator.next()
                    logger.debug("ENNNNNNNN %s" % token)
                elif next_token.type == "ASSIGN" or next_token.type == "APPEND":
                    # variable assignment analysis
                    is_assign = True if next_token.type == "ASSIGN" else False
                    value = _cache_check_assign(generator, var, lineno, next_token.value, ends=ends)
                    if value is not None:
                        # TODO: The assignment line actually should be saved.
                        logger.debug("ASSIGN value: %s=%s" % (var, value))
                        line = var + "=" + value
                        variables = dest_functions.get("variables", dict())
                        macros_line_analyze(line, variables, generator, self.options, self.reverses)
                    token = generator.next()
                else:
                    #TODO: 还可能是不含参数的函数
                    #unknown line
                    if token.type == "ID" and next_token.type in ends:
                        # Directly break
                        token = next_token
                        continue
                    # When start a new line, we should end up this loop.
                    one_word_line = True
                    sub_quotes_count = 0
                    logger.debug("quote count: %d" % sub_quotes_count)
                    token = next_token
                    while (token.type not in ends or sub_quotes_count > 0) \
                            and token.lineno == lineno:
                        if token.type in left:
                            sub_quotes_count += 1
                        elif token.type in right:
                            sub_quotes_count -= 1
                        token = generator.next()
                        logger.debug("quote count: %d" % sub_quotes_count)

                    logger.debug("Move outer token: %s" % token)

            elif token.type == "FUNC_ARG":
                logger.debug("## Start var line analysis %s" % token)
                lineno = token.lineno
                next_token = generator.next()
                if next_token.type in ends:
                    token = next_token
                    continue

                # When start a new line, we should end up this loop.
                sub_quotes_count = 0
                logger.debug("quote count: %d" % sub_quotes_count)

                token = next_token
                while (token.type not in ends or sub_quotes_count > 0) \
                        and token.lineno == lineno:
                    if token.type in left:
                        sub_quotes_count += 1
                    elif token.type in right:
                        sub_quotes_count -= 1
                    token = generator.next()
                    logger.debug("quote count: %d" % sub_quotes_count)
                logger.debug("Move outer token: %s" % token)

                # Skip part should be added to global quote_count
                paren_count += sub_quotes_count

            elif token.type == "MACROS":
                # 4. Analyze Macros assignment line.
                logger.debug("## Start Macros line analysis %s" % token)
                line = token.value
                variables = dest_functions.get("variables", dict())
                has_macros = True

                macros_line_analyze(line, variables, generator, self.options, self.reverses, is_macros_line=True)
                token = generator.next()

            elif token.type == "if":
                logger.debug("## Start if analysis.")
                status = self._check_sh_if(generator, level, func_name=func_name, allow_calling=allow_calling)
                if status:
                    token = generator.next()
                else:
                    token.type = "ID"
                    logger.debug("## End of if analysis fail. Try string analysis.")
                    continue
                logger.debug("## End of if analysis pass.")

            elif token.type == "case":
                logger.debug("## Start case analysis.")
                self._check_sh_case(generator, level, func_name=func_name, allow_calling=allow_calling)
                token = generator.next()
                logger.debug("## End of case analysis.")

            elif token.type == "for":
                logger.debug("## Start for analysis.")
                self._check_sh_for(generator, level, func_name=func_name, allow_calling=allow_calling)
                token = generator.next()
                logger.debug("## End of for analysis")

            elif token.type in left:
                logger.debug("## Start quote start line analysis.")
                lineno = token.lineno
                paren_count += 1
                next_token = generator.next()
                if next_token in ends:
                    token = next_token
                    break

                sub_quotes_count = 0
                logger.debug("quote count: %d" % sub_quotes_count)

                token = next_token
                while (token.type not in ends or sub_quotes_count > 0) \
                        and token.lineno == lineno:
                    if token.type in left:
                        sub_quotes_count += 1
                    elif token.type in right:
                        sub_quotes_count -= 1
                    token = generator.next()
                    logger.debug("quote count: %d" % sub_quotes_count)
                logger.debug("Move outer token: %s" % token)
                paren_count += sub_quotes_count

            elif token.type in right:
                paren_count -= 1
                # logger.debug("/\\ %s %d %s" % (token, quote_count, ends))
                if paren_count < 1 and token.type in ends:
                    break
                token = generator.next()

            else:
                # 4. Start with some undefined token, we maybe skip it.
                token = generator.next()

        if token.type in ends:
            # generator.seek(generator.index - 1)
            logger.debug("### END CALLING: %s" % token)
            return
        else:
            raise ParserError

    def _defined_macros_analyze(self, generator, macro_name, func_name, level, allow_defunc=False, allow_calling=False):
        """AC | AM macros we concerned, defined args fields in m4_macros_map."""
        if macro_name == "AC_DEFUN":
            logger.debug("## Start defined function analysis.")
            if allow_defunc:
                self._check_ac_defunc(generator)
            else:
                raise ParserError("Can't not calling AC_DEFUN here!")
        elif macro_name in ("AC_DEFINE", "AC_DEFINE_UNQUOTED"):
            fields, analysis_types = fields_split(generator, m4_macros_map.get(macro_name, list()))
            if len(fields) < 1:
                raise ParserError

            option_name_gen = get_temp_generator(fields[0], generator)
            option_name = self._value_analyze(option_name_gen)

            value = "1"
            if len(fields) > 1:
                # with default value.
                value_gen = get_temp_generator(fields[1], generator)
                value = self._macros_value_analyze(value_gen)

            description = ""
            if len(fields) > 2:
                description_gen = get_temp_generator(fields[2], generator)
                description = self._string_analyze(description_gen)

            self.config_h[option_name] = {
                "value": value,
                "description": description,
                "option": copy.deepcopy(self.options),
                "reverse": copy.deepcopy(self.reverses)
            }
        else:
            fields, analysis_types = fields_split(generator, m4_macros_map.get(macro_name, list()))
            if len(fields) == 0:
                # Calling function without args.
                pass
            field_defined = m4_macros_map.get(macro_name, list())
            if len(fields) > len(field_defined) // 2:
                raise ParserError

            for i, field in enumerate(fields):
                analysis_type = field_defined[i * 2]
                is_essential = field_defined[i * 2 + 1]
                try:
                    if len(field) >= 2:
                        # move out the start-end sparens.
                        field = field[1:-1] if field[0].type == "LSPAREN" and field[-1].type == "RSPAREN" else field
                    gen = get_temp_generator(field, generator)
                    self.command_analyze(gen, analysis_type=analysis_type, func_name=func_name,
                                         level=level + 1, allow_defunc=False)
                except StopIteration:
                    logger.debug("Analyze field complete.")
            if allow_calling:
                self._calling_to_merge(func_name, macro_name)

    def _undefined_macros_analyze(self, generator, macro_name, func_name, level, allow_calling=False):
        fields, analysis_types = fields_split(generator, m4_macros_map.get(macro_name, list()))
        if len(fields) == 0:
            # Calling function without args.
            pass

        for field, analysis_type in zip(fields, analysis_types):
            try:
                if len(field) >= 2:
                    # move out the start-end sparens.
                    field = field[1:-1] if field[0].type == "LSPAREN" and field[-1].type == "RSPAREN" else field
                gen = get_temp_generator(field, generator)
                if analysis_type == "string":
                    self._string_analyze(gen)
                else:
                    self._default_analyze(gen, func_name, level=level + 1,
                                          allow_defunc=False, allow_calling=allow_calling)
            except StopIteration:
                logger.debug("Analyze %s field complete." % macro_name)

        if allow_calling:
            self._calling_to_merge(func_name, macro_name)
        return

    def _string_analyze(self, generator):
        logger.debug("## Start string analysis.")
        return self._value_analyze(generator, ends=["RSPAREN", "RPAREN"])

    def _macros_value_analyze(self, generator):
        return self._value_analyze(generator)

    def _value_analyze(self, generator, ends=None):
        if ends is None:
            ends = ["RSPAREN", "RPAREN", "COMMA"]

        value = []
        quote_count = 0
        token = generator.next()
        # TODO: 需要加上引号的考虑， 或者直接从generator里面提取原文本
        while token.type not in ends or quote_count != 0:
            value.append(token.value)
            if token.type in left:
                quote_count += 1
            elif token.type in right:
                quote_count -= 1

            try:
                token = generator.next()
            except StopIteration:
                break
        return " ".join(value)

    def _check_sh_if(self, generator, level, func_name=None, allow_calling=False):
        """Checking 'if... else... ' and update options, and reverses status."""
        index = generator.index
        option = _check_bool_expresion(generator)
        if option is None:
            logger.debug("This if may be string line.")
            generator.seek(index)
            return False
        self.options.append(option)
        self.reverses.append(False)
        end_flags = False
        while not end_flags:
            self.command_analyze(generator, analysis_type="default", func_name=func_name,
                                 level=level + 1, ends=["else", "elif", "fi"],
                                 allow_calling=allow_calling)
            generator.seek(generator.index - 1)
            token = generator.next()
            if token.type == "fi":
                self.options.pop()
                self.reverses.pop()
                end_flags = True
            elif token.type == "else":
                self.reverses[-1] = True
            elif token.type == "elif":
                option = _check_bool_expresion(generator)
                self.options[-1] = option
                self.reverses[-1] = False
            else:
                raise ParserError
        return True

    def _check_sh_case(self, generator, level, func_name=None, allow_calling=False):
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
                self.options.append(option)
                self.reverses.append(False)
                self.command_analyze(generator, analysis_type="default", func_name=func_name, level=level + 1,
                                     ends=["DOUBLE_SEMICOLON"], allow_calling=allow_calling)
                self.options.pop()
                self.reverses.pop()
                token = generator.next()

                if token.type == "esac":
                    end_flags = True
            logger.debug("### End of case calling.")
        except StopIteration:
            raise ParserError

    def _check_sh_for(self, generator, level, func_name=None, allow_calling=False):
        try:
            token = generator.next()
            token_list = []
            while token.type != "do":
                token_list.append(token.value)
                token = generator.next()

            self.command_analyze(generator, analysis_type="default", func_name=func_name, level=level + 1,
                                 ends=["done"], allow_calling=allow_calling)
            logger.debug("### End of for calling.")
        except:
            logger.warning("Error happen in for analysis.")
            raise

    def _calling_to_merge(self, func_name, funcname_tocall):
        """
            Calling m4 macros and merge variables dict.

            TODO: args can be used to expend macros with arguments.
        """
        tocall_function = self.m4_libs.get(funcname_tocall, dict())
        present_function = self.functions.get(funcname_tocall, dict())
        if len(tocall_function) == 0 and len(present_function) == 0:
            logger.debug("{} may be a builtin function or loading fail.".format(funcname_tocall))
        elif len(present_function) != 0:
            tocall_function = present_function

        # Step 1: Merge variables for called function and calling function
        dest_functions = self.functions.get(func_name, dict())
        dest_variables = dest_functions.get("variables", dict())
        variables = tocall_function.get("variables", dict())
        for var in variables:
            if var not in dest_variables:
                dest_variables[var] = {
                    "defined": [],
                    "undefined": [],
                    "option": {},
                    "is_replace": False
                }

            var_dict = variables.get(var, dict())
            dest_var_dict = dest_variables.get(var, dict())

            import queue
            option_queue = queue.Queue()

            (has_default, default_N) = _check_global_dict_empty(dest_var_dict)
            if has_default and var_dict.get("is_replace", False) and len(self.options) == 0:
                dest_var_dict["option"]["default_{}".format(default_N)] = {
                    True: {
                        "defined": var_dict.get("defined", []),
                        "undefined": var_dict.get("undefined", []),
                        "option": {},
                        "is_replace": False
                    },
                    False: {"defined": [], "undefined": [], "option": {}, "is_replace": False},
                }
                for option in var_dict["option"]:
                    if option not in dest_var_dict.get("option", dict()):
                        dest_var_dict["option"][option] = var_dict["option"][option]
                    else:
                        option_queue.put((var_dict["option"][option][True], dest_var_dict["option"][option][True]))
                        option_queue.put((var_dict["option"][option][False], dest_var_dict["option"][option][False]))
            else:
                present_dest_dict = dest_var_dict
                for (option, reverse) in zip(self.options, self.reverses):
                    if option not in dest_var_dict.get("option", dict()):
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
                    dest["defined"] = src.get("defined", list())
                    dest["undefined"] = src.get("undefined", list())
                else:
                    dest_defined = dest.get("defined", list())
                    dest_undefined = dest.get("undefined", list())
                    dest_defined.extend(src.get("defined", list()))
                    dest_undefined.extend(src.get("undefined", []))

                for option in src["option"]:
                    if option not in dest["option"]:
                        dest["option"][option] = src["option"][option]
                    else:
                        option_queue.put((src["option"][option][True], dest["option"][option][True]))
                        option_queue.put((src["option"][option][False], dest["option"][option][False]))

        # Step 2: Merge export variables
        export_vars_dict = tocall_function.get("export_variables", dict())
        for export_var in export_vars_dict:
            if "export_variables" not in dest_functions:
                dest_functions["export_variables"] = dict()

            if export_var not in dest_functions.get("export_variables", dict()):
                dest_functions["export_variables"][export_var] = {
                    "defined": [], "undefined":[], "option": {}, "is_replace": True
                }

        # Step 3: Merge export conditions
        export_condition_dict = tocall_function.get("export_conditions", dict())
        for export_condition in export_condition_dict:
            if "export_conditions" not in dest_functions:
                dest_functions["export_conditions"] = dict()

            if export_condition not in dest_functions.get("export_conditions", dict()):
                dest_functions["export_conditions"][export_condition] = {
                    "defined": [], "undefined":[], "option": {}, "is_replace": True
                }
        return True

    def _check_ac_defunc(self, generator):
        """Checking AC_DEFUN field"""
        check_next(generator, "LPAREN")
        # check_next(generator, "LSPAREN")
        has_sparen = False
        token = generator.next()
        if token.type == "LSPAREN":
            # with paren
            token = generator.next()
            has_sparen = True
        if token.type != "ID":
            raise ParserError
        func_name = token.value
        self.functions[func_name] = {
            "calling": [],
            "need_condition_var": [],
            "need_assign_var": [],
            "variables": {},
            "export_variables": {},
            "export_conditions": {}
        }
        if has_sparen:
            check_next(generator, "RSPAREN")
        check_next(generator, "COMMA")
        self.command_analyze(generator, analysis_type="default", func_name=func_name, level=1)
        generator.seek(generator.index - 1)
        check_next(generator, "RPAREN")
        return


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
        try:
            # May be an empty caches
            data = self._caches[self._index - 1]
        except IndexError:
            raise StopIteration
        self._index += 1
        self._set_max()
        logger.debug(data)
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

    @property
    def origin_data(self):
        return self._origin_data


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
