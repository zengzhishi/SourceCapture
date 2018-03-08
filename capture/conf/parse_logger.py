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


def getLogger(conf, logger_field="captureExample", new_output=None):
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
