# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: parse_logger.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-22 17:45:26
    @LastModif: 2018-01-29 18:20:38
    @Note:
"""

import sys
import logging
import logging.config


def get_log_level(level='debug'):
    """
    Set the log level for python Bokeh code.

    :param level:
    :return:
    """
    LEVELS = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warn': logging.WARNING,
        'error': logging.ERROR,
        'fatal': logging.CRITICAL,
        'none': None
    }
    return LEVELS[level]


default_level = get_log_level()
capture_logger = logging.getLogger("capture")

console_formatter = logging.Formatter(
    '%(message)s'
)
formatter = logging.Formatter(
    "%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s - %(message)s")


if default_level is not None:
    capture_logger.setLevel(default_level)
capture_logger.propagate = False


def addConsoleHandler(logger=None, levelname='info'):
    # if not capture_logger.handlers:
    default_handler = logging.StreamHandler()
    level = get_log_level(levelname)
    if level is not None:
        default_handler.setLevel(level)
    default_handler.setFormatter(console_formatter)
    if logger:
        logger.addHandler(default_handler)
    else:
        capture_logger.addHandler(default_handler)


addConsoleHandler()


def addFileHandler(filePath, logger_field="capture", format=None, levelname='none'):
    """
    Config logging.

    logger_field:           logger_name
    format:                 formatter for
    """
    logger = logging.getLogger(logger_field)

    if filePath:
        filehandler = logging.FileHandler(filePath, "w")
        if not format:
            filehandler.setFormatter(formatter)
        else:
            filehandler.setFormatter(format)
        level = get_log_level(levelname)
        if level is not None:
            filehandler.setLevel(level)
        logger.addHandler(filehandler)


def getLogger(conf, logger_field="capture", new_output=None):
    """
    Config logging.

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
