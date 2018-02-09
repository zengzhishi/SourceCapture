# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_logger.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-22 17:45:26
    @LastModif: 2018-01-29 18:20:38
    @Note:
"""

import logging
import logging.config
import ConfigParser

import re

level_maps = {
        "NOSET" : logging.NOTSET,
        "DEBUG" : logging.DEBUG,
        "INFO" : logging.INFO,
        "WARN" : logging.WARN,
        "ERROR" : logging.ERROR,
        "CRITICAL" : logging.CRITICAL
        }

# 目前只支持这样
handler_maps = {
        "FileHandler": logging.FileHandler,
        "StreamHandler": logging.StreamHandler,
        }


class LoggerAnalysis(object):
    def __init__(self, log_conf_path=None):
        if log_conf_path is not None:
            self._path = log_conf_path
            self._config()
        else:
            None

    def _basic_config(self):
        self._logger = logging.getLogger("Capture")
        None

    def _config(self):
        self._config = ConfigParser.ConfigParser()
        self._config.read(self._path)
        _loggers_str = self._config.get("loggers", "keys")
        _handlers_str = self._config.get("handlers", "keys")
        _formatters_str = self._config.get("formatters", "keys")
        self._loggers = _loggers_str.split(",")
        self._handlers = _handlers_str.split(",")
        self._formatters = _formatters_str.split(",")
        self._get_formatters()
        self._get_Handler()
        self._get_loggers()

    def _format_reader(self, field, key):
        """由于ConfigParser未能读取format，因此需要重新读取返回内容自己解析"""
        start = False
        with open(self._path, 'r') as _config_reader:
            for line in _config_reader:
                if line.strip('[] \n') == field:
                    start = True
                if start:
                    lst = line.split("=")
                    if lst[0].strip() == key:
                        return lst[1].strip('\'\n ')
        return ""

    def _get_formatters(self):
        self.formatters = {}
        for formatter in self._formatters:
            field = "formatter_" + formatter
            format_string = self._format_reader(field, "format")
            if format_string:
                self.formatters[formatter] = logging.Formatter(format_string)
            else:
                self.formatters[formatter] = logging.Formatter()

    def _get_loggers(self):
        self.loggers = {}
        for logger_name in self._loggers:
            field = "logger_" + logger_name
            options = self._config.options(field)
            logger = logging.Logger(logger_name)
            for option in options:
                if option == "level":
                    level = level_maps[self._config.get(field, "level")]
                    logger.level = level
                elif option == "propagate":
                    logger.propagate = self._config.getint(field, "propagate")
                elif option == "handlers":
                    handler_name = self._config.get(field, "handlers")
                    logger.addHandler(self.handlers[handler_name])
            self.loggers[logger_name] = logger

    def _get_Handler(self):
        self.handlers = {}
        for handler_name in self._handlers:
            field = "handler_" + handler_name
            handler_class_name = self._config.get(field, "class")
            if "args" in self._config.options(field):
                args_str = self._config.get(field, "args")[1:-1]
                path, mode = args_str.split(",")
                path = path.strip('"\' ')
                mode = mode.strip(' \'')
            handler = handler_maps[handler_class_name] (path, mode=mode)
            formatter_name = self._config.get(field, "formatter")
            handler.setFormatter(self.formatters[formatter_name])
            handler.level = level_maps[self._config.get(field, "level")]
            self.handlers[handler_name] = handler

    def get_Logger(self, name, filepath=""):
        """令Handler创建交由调用的程序所决定，而不是只能使用config文件中定义的路径"""
        logger = self.loggers[name]
        formatter = logger.handlers[0].formatter
        if filepath:
            rfh = logging.FileHandler(filepath, mode='w')
            rfh.setFormatter(formatter)
            logger.removeHandler(logger.handlers[0])
            logger.addHandler(rfh)
        return logger


def getLogger(conf, logger_field="captureExample", new_output=None):
    """
    配置log, 这里只针对FileHandler做修改

    conf:                   logging.conf配置文件路径
    logger_field:           logger_name
    new_output:             是否需要重新指定输出文件
    """
    logging.config.fileConfig(conf)
    logger = logging.getLogger(logger_field)

    if new_output:
        origin_handle = logger.handlers[0]
        if type(origin_handle) != logging.FileHandler:
            return

        new_handle = logging.FileHandler(new_output, origin_handle.mode)
        formatter = origin_handle.formatter
        new_handle.formatter = formatter

        if origin_handle.level:
            new_handle.level = origin_handle.level

        if origin_handle.encoding:
            new_handle.encoding = origin_handle.encoding

        logger.removeHandler(logger.handlers[0])
        logger.addHandler(new_handle)
    return logger


if __name__ == "__main__":
    pass


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent