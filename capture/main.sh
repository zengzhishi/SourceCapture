#!/bin/bash

############################################################################################################################
#
# 该脚本暂定为程序的入口，参数从这里输入，做了一些预定义操作之后，将配置输入给capture.py执行
# TODO: 脚本需要完成的工作
# 1. 读入预处理命令，比如cmake的预处理，参数输入，环境配置等
# 2. 创建目录，包括输入目录和make build目录等
# 3. 如果没有输入编译方式，如果扫描目录的结构，找到解析的类型
# 4. 如果如果build目录在项目根目录下，如何排除等
# 5. 根据编译器的选择来生成对应的默认预处理和capture 参数输入等
#
############################################################################################################################


ARGS=$( \
getopt \
-o s:i:t:h \
-- "$@" \
)

COMMAN_INFO="\"Capture can analyze destination project by cmake, autotools and original Makefile,
without execute 'make' to buildup project.
Analysis result will be output to output_path, including compile_command.json, project_scan.json and log file.

Example:

Use --help to show all available options!\""

ARGUMENTS_INFO="\"COMMAND LINE ARGUMENTS:
    -h, --help
        Show this message and exit.

    -i, --input-path
        Project path to be analized.

    -o, --output-path
        Project analisis result output path.

    -c, --compiler-id
        Compiler will be used for output command.
        Available options: [ \"GNU\", \"Clang\" ]

    -b, --build-type
        Project building method.
        Available options: [ \"cmake\", \"autotools\", \"make\" ]

    -p, --build-path
        If project is using outer projet building, 
        this argument will let system to scan Building info from outerproject.\""

####### Function Defines ########

BLACK=$(tput setaf 0)
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
LIME_YELLOW=$(tput setaf 190)
POWDER_BLUE=$(tput setaf 153)
BLUE=$(tput setaf 4) 
MAGENTA=$(tput setaf 5)
CYAN=$(tput setaf 6)
WHITE=$(tput setaf 7)
BRIGHT=$(tput bold)
NORMAL=$(tput sgr0)
BLINK=$(tput blink)
REVERSE=$(tput smso)
UNDERLINE=$(tput smul)

_echo() {
    if [ "X$1" = "X-n" ]; then 
        shift; printf "%s" "$@" 
    else 
        printf "%s\n" "$@" 
    fi
}

ERROR() {
    _echo "${BRIGHT}${RED}ERROR! ${NORMAL}${RED}$@${NORMAL}"
}

WARNING() {
    _echo "${BRIGHT}${YELLOW}WARNING! ${NORMAL}${YELLOW}$@${NORMAL}"
}

INFO() {
    _echo "${GREEN}$@${NORMAL}"
}

PRINT() {
    _echo "$@"
}


####### Args Handling #######
eval set -- "$ARGS"
while true; do
    case $1 in 
        -h|--help)
            PRINT ""
            PRINT "USAGE:"
            PRINT ""
            PRINT "`eval _echo "$COMMAN_INFO"`"
            PRINT ""
            PRINT "`eval _echo "$ARGUMENTS_INFO"`"
            PRINT ""
            exit 0
        ;;
        -i|--input-path)
            INPUT_PATH="$2"; shift; shift; continue
        ;;
        -o|--output-path)
            OUTPUT_PATH="$2"; shift; shift; continue
        ;;
        -b|--build-type)
            BUILD_TYPE="$2"; shift; shift; continue
        ;;
        -p|--build-path)
            BUILD_PATH="$2"; shift; shift; continue
        ;;
        -c|--compiler-id)
            COMPILER_ID="$2"; shift; shift; continue
            ;;
        --)
            break
        ;;
        *)
            PRINT ""
            PRINT ""
            ERROR "Wrong parameter! Usage:"
            PRINT ""
            PRINT "`eval _echo "$COMMON_INFO"`"
            PRINT ""
            exit 1
        ;;
    esac
done


####### PRE-ANALYSIS #######


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
