# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: macros_analysis.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-02-23 13:36:01
    @LastModif: 2018-02-23 13:36:01
    @Note:
"""

import sys
import os
import re
import lexer_macros


class MacrosAnalyzer(object):
    file_path = ""
    macros = {
        #key: macros_name
        #value: size(增加代码长度), {headers,}(条件编译内引入的额外头文件), {宏定义嵌套关系?}
    }

    def __init__(self, path=file_path):
        if path:
            self.file_path = path

    def building_macros(self):
        filein = open(self.file_path, "r")
        pre_macros = []
        pre_nums = []

        for line in filein:
            line = line.strip(" \t\n")
            line = re.sub(" +", " ", line)
            if re.match("\s*#\s*if", line):
                result = lexer_macros.get_macros(line)
                num = 0
                for obj in result:
                    pre_macros.append(obj)
                    num += 1
                    if obj not in self.macros:
                        self.macros[obj] = []
                pre_nums.append(num)
            elif re.match("\s*#\s*elif", line):
                pre_macros = pre_macros[:-(pre_nums[-1])]
                pre_nums = pre_nums[:-1]

                result = lexer_macros.get_macros(line)
                num = 0
                for obj in result:
                    pre_macros.append(obj)
                    num += 1
                    if obj not in self.macros:
                        self.macros[obj] = []
                pre_nums.append(num)
            elif re.match("\s*#\s*include\s*\<(.*)\>", line) and len(pre_macros) != 0:
                for obj in pre_macros:
                    self.macros[obj].append(re.match("\s*#\s*include\s*\<(.*)\>", line).group(1))
            elif re.match("\s*#\s*endif", line):
                pre_macros = pre_macros[:-(pre_nums[-1])]
                pre_nums = pre_nums[:-1]

        filein.close()

    def exclude(self):
        """exclude some macros"""
        # TODO: 定制一些规则，可以将一些明确不会在当前系统环境下使用到的宏定义去除
        pass

    def build_definitions(self):
        """TODO: 可以定制一种方案讲比较高置信度的组合先返回，采用生成器的方法"""

    def dump_macros(self):
        import json
        print json.dumps(self.macros)

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
