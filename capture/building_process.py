# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: building_process.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-22 15:38:16
    @LastModif: 2018-01-26 18:00:10
    @Note: 进程池管理类
"""

import os
import time
import multiprocessing
import queue
import logging

logger = logging.getLogger("capture")

# 默认配置
CPU_CORE_COUNT = multiprocessing.cpu_count()


class ProcessBuilder(object):
    """
        使用时，先继承该类，设置logger和进程锁数目，然后需要重写mission和run函数，决定任务分配和数据的保存等。
    """
    def __init__(self, process_logger=None, lock_nums=1, process_amount=CPU_CORE_COUNT):
        self.process_amount = process_amount
        self._manager = multiprocessing.Manager()
        # self._queue = self._manager.Queue()
        self._queue = queue.Queue()

        self._logger = logger

        if process_logger is None:
            self._process_logger = logger
        self.lock = [self._manager.Lock() for i in range(lock_nums)]     # 创建指定数目的锁

    def mission(self, queue, result, locks=[]):
        """多进程任务的执行"""
        pass

    def distribute_jobs(self, jobs):
        """任务分配，可以被重写，默认采用单条数据作为一个任务"""
        for job in jobs:
            self._queue.put(job)

    def log_mission(self, logger, level="debug", massage=""):
        """多进程读写日志"""
        log_function = getattr(logger, level.lower())
        log_function(massage)

    def log_total_missions(self, queue, check_interval=0.01):
        """定时报告整体任务完成度，可以被重写，默认检查总任务数完成百分比"""
        total_count = queue.qsize()
        if total_count == 0:
            self._logger.warning("No data in job queue.")
            return
        left_count = total_count
        last_time = left_count
        self._logger.info("Mission process: %f %%" % 0.0)
        while left_count != 0:
            if left_count != total_count and last_time != left_count:
                self._logger.info("Mission process: %f %%" % \
                    ((total_count - left_count) / float(total_count) * 100.0))
                last_time = left_count
            time.sleep(check_interval)
            left_count = queue.qsize()
        self._logger.info("Mission process: %f %%" % \
                ((total_count - left_count) / float(total_count) * 100.0))
        return

    def mission_logger(self, pipe, logger):
        """多进程任务执行日志打印进程"""
        raw_massage = pipe.recv()
        while len(raw_massage) != 1:
            level, massage = raw_massage
            self.log_mission(logger, level, massage)
            raw_massage = pipe.recv()
        self.log_mission(logger, "info", "End of logging process.")
        return

    def run(self, process_log_path=None, worker_num=CPU_CORE_COUNT):
        """
            开始执行任务，建议使用multiprocessing.Process执行任务
        """
        resultlist = self._manager.list()
        self._logger.info("Multiprocess mission Start...")
        start_time = time.clock()

        # 添加全局任务监控进程
        process_list = []
        p = multiprocessing.Process(target=self.log_total_missions, args=(self._queue,))
        process_list.append(p)
        p.start()

        for i in range(worker_num):
            p = multiprocessing.Process(target=self.mission,
                                        args=(self._queue, resultlist, self.lock,))
            process_list.append(p)
            p.start()

        for p in process_list:
            p.join()

        end_time = time.clock()
        self._logger.info("All Process Time: %f" % (end_time - start_time))
        self._logger.info("Multiprocess mission complete...")
        return resultlist

    def mission_test(self, case):
        _queue = self._manager.QUEUE()
        for line in case:
            _queue.put(line)
        return self.mission(_queue, self.lock)


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
