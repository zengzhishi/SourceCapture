# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: building_bool.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-22 15:38:16
    @LastModif: 2018-01-23 16:20:15
    @Note: 建立进程池来处理编译命令的构建
"""

import os
import multiprocessing

CPU_CORE_COUNT = multiprocessing.cpu_count()

class CommandBuilder(object):
    def __init__(self, process_amount=CPU_CORE_COUNT):
        self._pool = multiprocessing.Pool(process_amount)
        _manager = multiprocessing.Manager()
        self._queue = _manager.Queue()

    def init(self, output_path, source_paths, hash_names, flags):
        for compile_tuple in zip(source_paths, output_paths, flags):
            None
        return

    def mission(self, queue, lock):
        """编译命令构建任务, 需要重写"""
        None

    def run(self):
        self._pool.map(self.mission, (self._queue,lock,))



# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
