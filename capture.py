# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: capture.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-23 11:27:56
    @LastModif: 2018-01-23 14:09:38
    @Note:
"""

import os
import sys
import json

def commands_dump(output_path, source_files, commands, working_paths):
    """导出生成的编译命令
    Args:
        output_path:        输出路径
        source_files:       源文件
        commands:           编译命令
        working_paths:      命令执行路径
    """
    json_body = []
    for output_tuple in zip(source_files, commands, working_paths):
        json_data = {
                "directory": output_tuple[2],
                "command": output_tuple[1],
                "file": output_tuple[0]
                }
        json_body.append(json_data)
    with open(output_path, 'w') as fout:
        json.dump(json_body, fout, indent=4)
    return

def scan_data_dump(output_path, source_files, macros, include_files, \
        include_paths, is_has_config=False):
    """导出目录扫描数据
    Args:
        output_path:        输出路径
        source_files:       源文件
        macros:             宏定义(与源文件一一对应)
        include_files:      头文件
        include_paths:      系统头文件搜索路径
        is_has_config:      是否含有configure
    """
    if is_has_config:
        map_macros = map(lambda macro: macro + " -DHAVE_CONFIG_H", macros)
    else:
        map_macros = macros

    json_data = {
            "source_files": source_files,
            "macros": map_macros,
            "source_count": len(source_files),
            "include_files": include_files,
            "include_count": len(include_files),
            "include_paths": include_paths
            }

    with open(output_path, 'w') as fout:
        json.dump(json_data, fout, indent=4)
    return

class CaptureBuilder(object):
    None

def main():
    """主要逻辑"""


if __name__ == "__main__":
    main()


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
