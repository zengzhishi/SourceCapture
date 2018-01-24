# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: building_process.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-22 15:38:16
    @LastModif: 2018-01-24 17:48:22
    @Note: 进程池管理类
"""

import os
import time
import multiprocessing


# 使用copy_reg将MethodType注册为可序列化的方法，从而保证类方法可以被pickle序列化
import copy_reg
import types

def _pickle_method(m):
    if m.im_self is None:
        return getattr, (m.im_class, m.im_func.func_name)
    else:
        return getattr, (m.im_self, m.im_func.func_name)

copy_reg.pickle(types.MethodType, _pickle_method)

# 默认配置
CPU_CORE_COUNT = multiprocessing.cpu_count()


class ProcessBuilder(object):
    """
        使用时，先继承该类，设置logger和进程锁数目，然后需要重写mission和run函数，决定任务分配和数据的保存等。
    """
    def __init__(self, logger, lock_nums=1, process_amount=CPU_CORE_COUNT):
        self.process_amount = process_amount
        self._manager = multiprocessing.Manager()
        self.queue = self._manager.Queue()
        self._logger = logger
        self._logger_lock = self._manager.Lock()
        self.lock = [self._manager.Lock() for i in range(lock_nums)]     # 创建指定数目的锁
        self._basic_config()

    def _basic_config(self):
        self.LOGGER_LEVEL = {
            "critical" : self._logger.critical,
            "error" : self._logger.error,
            "warning" : self._logger.warning,
            "info" : self._logger.info,
            "debug" : self._logger.debug,
            }

    def mission(self, queue, locks=[]):
        """多进程任务的执行"""
        None

    def distribute_jobs(self, jobs):
        """任务分配，可以被重写，默认采用单条数据作为一个任务"""
        for job in jobs:
            self.queue.put(job)
        self.total_count = self.queue.qsize()

    def log_mission(self, level, massage):
        """多进程读写日志"""
        self._logger_lock.acquire()
        self.LOGGER_LEVEL[level](massage)
        self._logger_lock.release()

    def log_total_missions(self, queue, check_interval=0.01):
        """定时报告整体任务完成度，可以被重写，默认检查总任务数完成百分比"""
        left_count = queue.qsize()
        while left_count != 0:
            self.log_mission("info", "Mission process: %f %%" % \
                    ((self.total_count - left_count) / float(self.total_count) * 100.0))
            time.sleep(check_interval)
            left_count = queue.qsize()
        self.log_mission("info", "Mission process: %f %%" % \
                ((self.total_count - left_count) / float(self.total_count) * 100.0))
        return

    def run(self, worker_num=CPU_CORE_COUNT):
        """
            开始执行任务，建议使用multiprocessing.Process执行任务
        """
        resultlist = self._manager.list()
        self.log_mission("info", "Multiprocess mission Start...")
        start_time = time.clock()

        process_list = []
        for i in range(worker_num):
            p = multiprocessing.Process(target=self.mission, args=(self.queue, resultlist, self.lock,))
            process_list.append(p)
            p.start()

        for p in process_list:
            p.join()

        end_time = time.clock()
        self.log_mission("info", "All Process Time: %f" % (end_time - start_time))
        self.log_mission("info", "Multiprocess mission complete...")
        return resultlist


    def mission_test(self, case):
        _queue = self._manager.QUEUE()
        for line in case:
            _queue.put(line)
        return self.mission(_queue, self.lock)


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
