=============
SourceCapture
=============

A compiler command building project.


说明
========

capture 能捕获一个 Makefile, CMake, Autotools 和 SConstruct 构建的项目中，源文件的编译命令，生成compile_command.json文件，并存储项目的扫描统计数据。
python 版本支持 Python 3.6.2 

* requirements.txt 中是capture执行时，依赖的模块

Usage
=====

使用build_capture.py作为入口，使用时先保证目标扫描项目已经配置完成::

    python build_capture.py ${project_root_path} ${result_output_path}


其中

* project_root_path 项目根目录
* result_output_path 输出目录

其他还有更加详细的使用请使用::

    python build_capture.py -h
    或
    python build_capture.py --help

来查看
