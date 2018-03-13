# -*- coding:utf-8 -*-
"""
 Copyright (C), 2016-2017, Sourcebrella, Inc Ltd - All rights reserved.
 Unauthorized copying, using, modifying of this file, via any medium is strictly prohibited.
 Proprietary and confidential.

 Author: Nianwu Wang<chrlis@sbrella.com>
 File Description: Create compile and link dependencies graph, and built by task pool automatically. Also,
    it can generate some visual debug information.
 Creation Date: 2017-08-09
 Modification History:
    chrlis, create python script.
"""

import os
import signal
import psutil
import time


class Register(object):
    def __init__(self):
        self.__pid_time_maps = dict()
        self.__gpid_time_maps = dict()

    def register_pid(self, pid):
        """ """
        # print("register pid: %s." % pid)
        if pid is None:
            raise Exception("Register invalid pid.")
        self.__pid_time_maps[pid] = time.time()

    def deregister_pid(self, pid):
        """ """
        # print("un register pid: %s." % pid)
        if pid is None:
            raise Exception("Deregister invalid pid.")
        self.__pid_time_maps.pop(pid)

    def register_gpid(self, gpid):
        """ """
        # print("register gpid: %s." % gpid)
        if gpid is None:
            raise Exception("Register invalid gpid.")
        self.__gpid_time_maps[gpid] = time.time()

    def deregister_gpid(self, gpid):
        """ """
        # print("un register gpid: %s." % gpid)
        if gpid is None:
            raise Exception("Deregister invalid gpid.")
        self.__gpid_time_maps.pop(gpid)

    @staticmethod
    def __terminate_pid(pid):
        """ """
        if os.getpgid(pid) == pid:
            raise Exception("Can not interrupt a group process.")
        os.kill(pid, signal.SIGKILL)

    @staticmethod
    def __terminate_gpid(gpid):
        """ """
        if os.getpgid(gpid) != gpid:
            raise Exception("Can not interrupt a no-group process.")
        os.killpg(gpid, signal.SIGKILL)

    def terminate_large_memory_process(self, percent=94):
        """ Largest percent 94%. """
        svmem = psutil.virtual_memory()
        max_memory_used_pid = None
        max_memory_pid_used = 0
        max_memory_used_gpid = None
        max_memory_gpid_used = 0

        if svmem.percent > percent:
            for pid in self.__pid_time_maps.keys():
                p = psutil.Process(pid=pid)
                if p.memory_info().rss > max_memory_pid_used:
                    max_memory_pid_used = p.memory_info().rss
                    max_memory_used_pid = pid

            for gpid in self.__gpid_time_maps.keys():
                gp = psutil.Process(pid=gpid)

                # All the children is in the same group[must]
                children = gp.children(recursive=True)
                cur_rss = gp.memory_info().rss
                for child in children:
                    cur_rss += child.memory_info().rss
                if cur_rss > max_memory_gpid_used:
                    max_memory_gpid_used = cur_rss
                    max_memory_used_gpid = gpid

        if max_memory_used_pid:
            self.__terminate_pid(max_memory_used_pid)
        if max_memory_used_gpid:
            self.__terminate_gpid(max_memory_used_gpid)

    def terminate_long_time_process(self, timeout=900):
        """ Time out 15 min. """
        end_time = time.time()
        for pid, start_time in self.__pid_time_maps.items():
            consume_time = end_time - start_time
            if consume_time > timeout:
                # Only one, it will change 'self.__pid_time_maps'
                self.__terminate_pid(pid=pid)
                break

        for gpid, start_time in self.__gpid_time_maps.items():
            consume_time = end_time - start_time
            if consume_time > timeout:
                # Only one, it will change 'self.__pid_time_maps'
                self.__terminate_gpid(gpid=gpid)
                break

    def _terminating(self):
        """ Call it while catching an interruption or abort. """
        cur_process_pid = os.getpid()
        cur_process_gpid = os.getpgrp()

        for pid in self.__pid_time_maps:
            if pid == cur_process_pid:
                raise Exception("Can not kill the current process.")
            try:
                self.__terminate_pid(pid)
            except ProcessLookupError:
                pass

        for gpid in self.__gpid_time_maps:
            if gpid == cur_process_gpid:
                raise Exception("Can not kill the current process group.")
            try:
                self.__terminate_gpid(gpid)
            except ProcessLookupError:
                pass
