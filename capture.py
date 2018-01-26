# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: capture.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-23 11:27:56
    @LastModif: 2018-01-26 19:02:13
    @Note:
"""

import os
import sys
import logging
import logging.config

import hashlib
import json

# 需要改为绝对路径
import parse_logger
try:
    import redis
except ImportError:
    sys.path.append("./utils")
    import redis


# 基本配置项
CONFIG_FILE = "./capture.cfg"


def bigFileMD5Calc(file):
    """逐步更新计算文件MD5"""
    m = hashlib.md5()
    buffer = 8192   # why is 8192 | 8192 is fast than 2048

    m.update(file)  # 加入文件的路径，使得不同目录即使文件内容相同，也能生成不同的MD5值
    with open(file, 'rb') as f:
        while True:
            chunk = f.read(buffer)
            if not chunk:
                break
            m.update(chunk)

    return m.hexdigest()


def fileMD5Calc(file):
    """直接读取计算文件MD5"""
    m = hashlib.md5()
    m.update(file)
    with open(file, 'rb') as f:
        m.update(f.read())

    return m.hexdigest()


def source_path_MD5Calc(file):
    """直接计算文件路径的MD5，不考虑文件内容，只要能对文件就行重新命令即可"""
    m = hashlib.md5()
    m.update(file)
    return m.hexdigest()


def file_transfer(filename, path):
    """文件名转换"""
    file = path + "/" + filename, "rb"
    statinfo = os.stat(file)
    if int(statinfo.st_size) / 1024 * 1024 >= 1:
        print "File size > 1M, use big file calc"
        return bigFileMD5Calc(file)
    return fileMD5Calc(file)


def file_info_save(redis_instance, filename, source_path, transfer_name, definition, flags):
    """保存源文件信息到redis中"""
    seria_data = (source_path, filename, definition, flags)
    redis_instance.set(transfer_name, json.dumps(seria_data))
    return

def get_file_info(redis_instance, transfer_name):
    """利用transfer_name获取源文件编译信息
    Returns:
        source_path:    源文件路径
        filename:       文件名
        definition:     宏定义
        flags:          编译参数
    """
    raw_data = redis_instance.get(transfer_name)
    seria_data = json.loads(raw_data)
    return seria_data


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


def dict_command_dump(output_path, result_dict):
    """利用最终返回的结果字典，导出生成的编译命令"""
    json_body = []
    while len(result_dict):
        key, output_tuple = result_dict.popitem()
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
    """主要的编译构建脚本生成类"""
    def __init__(self, compiler_type="gcc", compiler_path=None):
        self.__prefers = []
        self.compiler_type = compiler_type
        if compiler_path:
            self.compiler_path = compiler_path
        else:
            self.compiler_path = get_system_compiler_path(compiler_type)

    def __logger_config(self):
        pass

    def add_prefer_folder(self, folder):
        self.__prefers.append(folder)
        pass

    @prefers.setter
    def prefers(self, prefers):
        import types
        if type(prefers) == types.ListType:
            self.__prefers = prefers
        else:
            raise TypeError("object 'prefers' is not ListType")

    @property
    def prefer_folders(self):
        return self.__prefers

    def command_prebuild(self, ):
        pass

def get_system_compiler_path(compiler_type):
    """获取系统自带的编译器路径"""
    pass

def parse_prefer_str(prefer_str, input_path):
    if prefer_str == "all":
        prefers = source_detective.get_dir(input_path)
    else:
        prefers = prefer_str.strip(' \n\t').split(",")
    return prefers

def main():
    """主要逻辑"""


if __name__ == "__main__":
    main()


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
