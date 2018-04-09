# -*- coding:utf-8 -*-
"""
 Copyright (C), 2016-2017, Sourcebrella, Inc Ltd - All rights reserved.
 Unauthorized copying, using, modifying of this file, via any medium is strictly prohibited.
 Proprietary and confidential.

 Author: Nianwu Wang<chrlis@sbrella.com>
 File Description: Create compile and link dependencies graph, and built by task pool automatically. Also,
    it can generate some visual debug information.
 Creation Date: 2017-07-25
 Modification History:
    chrlis, add python script.
"""

import logging
import multiprocessing
import queue
import signal
import threading
import time

from capture.pool.register import Register


class Pool(Register):
    def __init__(self, entry, pool_size=multiprocessing.cpu_count()):
        super().__init__()
        self.__work_queue = queue.Queue()
        self.__thread_entry = entry
        self.__thread_pool_size = pool_size if pool_size <= multiprocessing.cpu_count() \
            else multiprocessing.cpu_count()
        self.__thread_terminated = True
        self.__threads = list()

        self.__int_sig_handle = None
        self.__term_sig_handle = None

    def _register_signal_handle(self):
        """ """
        self.__int_sig_handle = signal.signal(signal.SIGINT, self.__signal_handle)
        self.__term_sig_handle = signal.signal(signal.SIGTERM, self.__signal_handle)

    def _unregister_signal_handle(self):
        """ """
        if not self.__int_sig_handle:
            signal.signal(signal.SIGINT, self.__int_sig_handle)
            self.__int_sig_handle = None
        if not self.__term_sig_handle:
            signal.signal(signal.SIGTERM, self.__term_sig_handle)
            self.__term_sig_handle = None

    def __signal_handle(self, signal_num):
        """ Catch interrupt and break the thread pool immediately.
        """
        msg = "Catches a signal(interrupt): %d" % signal_num
        logging.critical(msg=msg)

        self._unregister_signal_handle()
        if not self.is_terminated:
            self.set_terminated()
            self._terminating()
            logging.info("The private thread pool has been broken.")
        raise KeyboardInterrupt(msg)

    @property
    def thread_pool_size(self):
        return self.__thread_pool_size

    def init_thread_pool(self, *args):
        """ Create the thread pool and start it.
        """
        self.__thread_terminated = False
        logging.info("The private thread pool size is : %d." % self.__thread_pool_size)

        self._register_signal_handle()
        for i in range(self.__thread_pool_size):
            thread = threading.Thread(target=self.__thread_entry, args=args)
            thread.start()
            self.__threads.append(thread)
        logging.info("The private thread pool has been inited.")

    def join_thread_pool(self):
        """ 1 Wait for the empty of work queue.
            2 Set the stop flag of thread loop.
            3 Join the threads.
        """
        while self.__work_queue and not self.__work_queue.empty():
            time.sleep(0.02)

        self.__thread_terminated = True     # The thread is waiting for terminate signal.
        for thread in self.__threads:
            thread.join()
        self._unregister_signal_handle()
        self.__threads = list()
        logging.info("The private thread pool has been destroyed.")

    def add_item(self, data):
        """ Insert the task into the work queue. The size of queue is unlimited.
        """
        if self.__work_queue:
            self.__work_queue.put(data)

    def get_item(self, block=True, timeout=None):
        """ Get the task from the work queue.
        """
        if self.__work_queue:
            return self.__work_queue.get(block=block, timeout=timeout)
        else:
            raise ValueError("Can not find the Queue.")

    def set_terminated(self):
        """ Set the flag to break the thread pool by the user.
        """
        self.__thread_terminated = True
        self.__work_queue = None

    @property
    def is_terminated(self):
        """ Get status whether the thread pool is broken.
        """
        return self.__thread_terminated


def woker():
    global queue_get_item
    threadname = threading.currentThread().getName()
    print(threadname)

    stop_flags = False
    while not stop_flags:
        try:
            item = queue_get_item(timeout=0.5)
            print(item)
        except queue.Empty:
            stop_flags = True


if __name__ == "__main__":
    lines = [
        "12222222222222222222222222222222222",
        "jklsdkfljfalkjlajlfdjlkasjl",
        "jklsdjfalkjlajejrlwkejr",
        "jklsdjfalkjlajlfdjlkasjl",
        "jkekjflewjlrjwqlekrjlqk",
        "jklsdjfalkjlajlfdjlkasjl",
        "asdkfldjfalkjlajlfdjlkasjl",
        "jklsdjfalsjdifoli",
        "jklsdjfalkjlajlfjio132kkk",
    ]

    pool = Pool(woker)
    queue_get_item = pool.get_item
    for line in lines:
        pool.add_item(line)
    pool.init_thread_pool()
    pool.join_thread_pool()

