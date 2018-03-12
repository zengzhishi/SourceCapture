# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: capture_util.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-03-12 10:53:39
    @LastModif: 2018-03-12 10:55:18
    @Note:
"""

import subprocess
import logging

logger = logging.getLogger("capture")


def subproces_calling(cmd="", cwd=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT):
    try:
        if cwd:
            p = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=stdout, stderr=stderr)
        else:
            p = subprocess.Popen(cmd, shell=True, stdout=stdout, stderr=stderr)

        out, err = p.communicate()

        return p.returncode, out, err
    except (OSError, ValueError, subprocess.TimeoutExpired):
        logger.warning("Subprocess command:[%s] execute fail" % cmd)
        return -1, None, None


# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
