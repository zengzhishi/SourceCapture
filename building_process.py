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
import parse_logger

# 使用copy_reg将MethodType注册为可序列化的方法，从而保证类方法可以被pickle序列化
"""
import copy_reg
import types

def _pickle_method(m):
    if m.im_self is None:
        return getattr, (m.im_class, m.im_func.func_name)
    else:
        return getattr, (m.im_self, m.im_func.func_name)

copy_reg.pickle(types.MethodType, _pickle_method)
"""

# 默认配置
CPU_CORE_COUNT = multiprocessing.cpu_count()
MASSAGE_SEPERATE = ";;"

class ProcessBuilder(object):
    """
        使用时，先继承该类，设置logger和进程锁数目，然后需要重写mission和run函数，决定任务分配和数据的保存等。
    """
    def __init__(self, logger=None, process_logger=None, lock_nums=1, process_amount=CPU_CORE_COUNT):
        self.process_amount = process_amount
        self._manager = multiprocessing.Manager()
        self._queue = self._manager.Queue()

        if logger is None:
            logger = self._logger_config()
        self._logger = logger

        if process_logger is None:
            self._process_logger = logger
        self.lock = [self._manager.Lock() for i in range(lock_nums)]     # 创建指定数目的锁

    def _logger_config(self, process_log_path=None):
        try:
            logger_builder = parse_logger.logger_analysis("capture.cfg")
        except:
            self._logger.warning("Logger configure fail")
            import logging
            return logging.getLogger("Capture")

        if not process_log_path:
            logger = logger_builder.get_Logger("simpleExample", "capture.log")
        else:
            logger = logger_builder.get_Logger("processLogger", \
                    process_log_path + "/process.log")
        return logger

    def mission(self, queue, result, locks=[]):
        """多进程任务的执行"""
        None

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
        last_time = total_count
        left_count = total_count
        self._logger.info("Mission process: %f %%" % 0.0)
        while left_count != 0:
            if left_count != total_count:
                self._logger.info("Mission process: %f %%" % \
                    ((total_count - left_count) / float(total_count) * 100.0))
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

        # # 设置进程日志
        # if not process_log_path:
        #     filepath = self._logger.handlers[0].baseFilename
        #     filename = filepath.split("/")[-1]
        #     process_log_path = filepath[:-(len(filename) + 1)]
        # process_logger = self._logger_config(process_log_path)
        #
        # # 设置日志信息管道
        # self.__logger_pipe_r, self.__logger_pipe_w = multiprocessing.Pipe(duplex=False)

        # 添加全局任务监控进程
        process_list = []
        p = multiprocessing.Process(target=self.log_total_missions, \
                args=(self._queue,))
        process_list.append(p)
        p.start()

        for i in range(worker_num):
            p = multiprocessing.Process(target=self.mission, \
                                        args=(self._queue, resultlist, \
                                        self.lock,))
            process_list.append(p)
            p.start()

        # # 添加进程任务打印进程  TODO: 考虑是否可合并
        # p_logger = multiprocessing.Process(target=self.mission_logger, \
        #         args=(self.__logger_pipe_r, process_logger,))
        # p_logger.start()

        for p in process_list:
            p.join()

        # 在其他进程结束之后对日志模块发出结束信号
        # self.__logger_pipe_w.send("END")
        # p_logger.join()


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
