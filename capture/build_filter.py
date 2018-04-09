# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: build_filter.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-02-22 15:47:38
    @LastModif: 2018-02-22 15:54:52
    @Note: filter unchanged source file.
"""

import os
import sys
import time

try:
    import redis
except ImportError:
    sys.path.append("./util/redis")
    import redis

import logging
logger = logging.getLogger("capture")


def _action(action, *args, **kwargs):
    try:
        result = action(*args, **kwargs)
        return True, result
    except(ConnectionError, TimeoutError, redis.ResponseError):
        return False, None


class BuildFilter(object):
    """Check file update time, and filter file need to update"""
    default_time = time.time()

    def __init__(self, output_path, action_timeout=0.1, host="localhost", port=6379, name_map_db=2, update_time_db=3):
        """
        :param host:
        :param port:
        :param name_map_db:                     redis database for file_name mapping
        :param update_time_db:                  redis database for saving file updated time
        """
        self._output_path = output_path
        self._redis_filename = redis.Redis(host=host, port=port, db=name_map_db)
        self._redis_update_time = redis.Redis(host=host, port=port, db=update_time_db)
        self._timeout = action_timeout

    def get_update_time(self, file_code):
        last_update_time = self._do_action(self._redis_update_time.get, file_code)
        return float(last_update_time) if last_update_time else self.default_time

    def check_update_time(self, file_code):
        """check file modify time"""
        file_path = self._do_action(self._redis_filename.get, file_code)
        if not file_path or not os.path.exists(file_path):
            logger.warning("File: {} is not exist.".format(file_path))
            return False

        output_filepath = os.path.join(self._output_path, file_code + ".o")
        output_bc_filepath = os.path.join(self._output_path, file_code + ".bc")
        mtime = os.path.getmtime(file_path)
        last_mtime = self.get_update_time(file_code)
        if os.path.exists(output_filepath) or os.path.exists(output_bc_filepath):
            return True if mtime != last_mtime else False
        else:
            return True

    def set_update_time(self, file_code, file_path):
        if not os.path.exists(file_path):
            logger.warning("set File: {} update time fail.".format(file_path))
            return
        mtime = os.path.getmtime(file_path)
        self._do_action(self._redis_update_time.set, file_code, mtime)

    def update_file_mapping(self, file_codes, compile_commands):
        for tuple in zip(file_codes, compile_commands):
            file_code = tuple[0]
            json_obj = tuple[1]
            file_path = json_obj["file"]
            self._do_action(self._redis_filename.set, file_code, file_path)

    def _do_action(self, action, *args, **kwargs):
        times = 0
        status, result = _action(action, *args, **kwargs)
        while not status and times < 3:
            logger.warning("Redis: action: {} args: {} {} fail. Try times: {}".format(action.__name__, args, kwargs, times))
            time.sleep(self._timeout)
            times += 1
            status, result = _action(action, *args, **kwargs)
        return result

    def filter_building_source(self, file_codes, compile_commands, update_all=False):
        """

        :param file_codes:
        :param compile_commands:
        :param update_all:
        :return:
            need_compile_commands:      compile_command in compile_commands needed to update
        """
        need_compile_commands = []
        files = []

        if update_all:
            self._redis_filename.flushall()
            self._redis_update_time.flushall()

        if self._redis_filename.dbsize() != len(file_codes):
            self.update_file_mapping(file_codes, compile_commands)

        for tuple in zip(file_codes, compile_commands):
            file_code = tuple[0]
            json_obj = tuple[1]
            file_path = json_obj["file"]
            if self.check_update_time(file_code):
                need_compile_commands.append(json_obj)
            files.append(file_path)

        for tuple in zip(file_codes, files):
            self.set_update_time(tuple[0], tuple[1])

        self._do_action(self._redis_filename.save)
        self._do_action(self._redis_update_time.save)

        return need_compile_commands


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
