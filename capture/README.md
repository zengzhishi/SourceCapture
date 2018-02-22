# Rebuild compile unit

### 阶段目标
不读取 .h 和 .c 文件构建一份编译命令脚本，使得gcc -c命令能够全部正确执行，生成对应的.o文件 \
~~编译命令应当从json和redis中读取来动态构建命令并执行（并行）~~
CMake项目基本能扫描完整
Makefile直接构建的项目能提取比较完整的命令参数

### TODO list
1. ~~日志模块的完善~~
2. ~~building_process模块目前还需要重复写很多地方，需要再抽象~~
3. ~~source_detective.py过于臃肿，需要分离很多东西，将该模块还原会原来定义的文件识别扫描功能~~
4. ~~cfg文件定义的日志模板需要优化一下~~
5. ~~需要加入编译的并行化，目前只完成了构建命令的并行化~~
6. ~~CMake项目需要添加单独处理~~
7. ~~需要将原来的绝对路径修改为相对路径~~
8. 整理新的项目扫描统计的输出格式 **doing**
9. cmake的命令执行过程中可能会出现自动生成的源文件，这部分要如何处理，需要调研一下(example: blender项目) **delay**
10. 项目执行入口需要完善，main.sh **delay**
11. ~~automake项目的方案解决 **close**, 直接使用和make兼容的方式即可，后续有需求才可能重开.~~
12. ~~Makefile直接构建项目的解决 **delay**~~
13. 数据导出模块需要修改一下 **doing**
14. ~~automake项目的输出结果如何与cmake，makefile项目兼容，需要设计一下~~
15. ~~automake项目和Makefile项目统一做成make -Bnkw的方式， cmake可以暂时保留这种方式~~
16. ~~另外扫描目录的逻辑需要保留并与make -Bnkw的进行结合~~
17. ~~gcc命令解析需要重新完善一下~~
18. make命令解析部分需要完善对cmake生成的命令的兼容，主要处理cd到某个路径执行的问题，虽然大部分项目采用的是绝对路径执行，但是仍然不排除会出现影响的情况
19. scons构建工具的调研和集成如capture中 **delay: 暂时找不到比较像样的scons构建项目**
20. ~~命令行输入的设置需要完善，简化 **done**~~
21. ~~suffix, preffix从配置文件读取的功能需要完善 **doing**~~
22. ~~文件更新时间的检查，增量构建，实现make的简化功能，只检查源文件和头文件（是否需要呢？）是否更新 **done**~~ ps: 头文件的检查不读取源文件没法做，不符合现在的项目目标，因此暂时不做头文件的检查
23. link的解析问题，需要开始调研
24. 考虑加入更加高级的模式，通过构建宏定义的语法树来生成可能的构建方案，提供给用户这种方式（针对没有任何构建工具的裸代码）

### 依赖模块
* 这里依赖了[redis](https://pypi.python.org/pypi/redis/2.10.6)模块，如果有该模块的则可以直接使用，否则需要去git clone https://github.com/andymccurdy/redis-py 项目下来，并将redis目录放到utils目录下，这样项目就能引入该模块来使用 \
之所以这么麻烦是当心之后可能需要对redis client进行精简
* make -Bnkw的方式获取的命令解析参考了[compiledb-generator](https://github.com/nickdiego/compiledb-generator)
