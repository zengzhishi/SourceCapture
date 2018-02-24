import ply.lex as lex

# List of token names.   This is always required
reserved = {
    "if": "if",
    "elif": "elif",
    "ifdef": "ifdef",
    "ifndef": "ifndef",
    "defined": "defined"
}

tokens = [
    'SHAPE',
    'AND',
    'OR',
    'MACROS',
    'LPAREN',
    'RPAREN',
    'NUMBER',
    'LARGER',
    'LESS',
    'LARGER_AND_EQUAL',
    'LESS_AND_EQUAL',
    'NOT_EQUAL',
    'EQUAL',
    'COMMENT',
    'INCLUDE_COMMENT',
    'NOT',
]

tokens += list(reserved.values())

# Regular expression rules for simple tokens
t_SHAPE = r'\#'
t_AND = r'&&'
t_OR = r'\|\|'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LARGER = r">"
t_LARGER_AND_EQUAL = r">="
t_LESS = r'<'
t_LESS_AND_EQUAL = r'<='
t_NOT_EQUAL = r'\!='
t_EQUAL = r'=='
t_COMMENT = r'//.*'
t_INCLUDE_COMMENT = r'/\*.*\*/'
t_NOT = r'\!'


def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t


def t_MACROS(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    t.type = reserved.get(t.value,'MACROS')
    return t


# A string containing ignored characters (spaces and tabs)
t_ignore  = ' \t'


# Error handling rule
def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)


# Build the lexer
lexer = lex.lex()


def get_macros(line):
    data = line.strip()

    # Give the lexer some input
    lexer.input(data)

    macros = []
    has_defined = False
    # Tokenize
    while True:
        tok = lexer.token()
        if not tok:
            break      # No more input
        if tok.type == "MACROS":
            macros.append(tok.value)
        elif tok.type in ["defined", "ifdef", "ifndef"]:
            has_defined = True

    if has_defined:
        return macros
    else:
        return []
