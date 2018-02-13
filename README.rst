=============
SourceCapture
=============


.. image:: https://img.shields.io/pypi/v/capture.svg
        :target: https://pypi.python.org/pypi/capture

.. image:: https://img.shields.io/travis/zengzhishi/capture.svg
        :target: https://travis-ci.org/zengzhishi/capture

.. image:: https://readthedocs.org/projects/capture/badge/?version=latest
        :target: https://capture.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status




A compiler command building project.


* Free software: MIT license
* Documentation: https://capture.readthedocs.io.


说明
========

SourceCapture 能捕获一个Makefile构建的项目中，源文件的编译命令，生成compile_command.json文件，并存储项目的扫描统计数据。

* requirements.txt 中是capture执行时，依赖的模块

Usage
=====

使用capture.py作为入口（main.sh 暂时用不了），使用时先保证目标扫描项目已经配置完成::

    python capture.py ${project_root_path} ${prefers} ${result_output_path} ${build_type} ${build_path} ${compiler_id}

其中

* project_root_path 项目根目录
* prefers 关注目录，以逗号分割 [ all 代表全部目录扫描 ]
* result_output_path 输出目录
* build_type 构建方式（cmake， make， scons[暂未完成]），其中使用 autotools 构建的，并未做单独处理，请生成了Makefile之后使用make
* build_path 执行构建命令的目录
* compiler_id 编译器类型（目前支持GNU GCC 和 Clang） GNU GCC请输入GNU， Clang请输入Clang
