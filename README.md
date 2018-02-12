# Rebuild compile unit

### 阶段目标
不读取 .h 和 .c 文件构建一份编译命令脚本，使得gcc -c命令能够全部正确执行，生成对应的.o文件 \
~~编译命令应当从json和redis中读取来动态构建命令并执行（并行）~~
CMake项目基本能扫描完整

### TODO list
1. ~~日志模块的完善~~
2. ~~building_process模块目前还需要重复写很多地方，需要再抽象~~
3. ~~source_detective.py过于臃肿，需要分离很多东西，将该模块还原会原来定义的文件识别扫描功能~~
4. ~~cfg文件定义的日志模板需要优化一下~~
5. ~~需要加入编译的并行化，目前只完成了构建命令的并行化~~
6. ~~CMake项目需要添加单独处理~~
7. ~~需要将原来的绝对路径修改为相对路径~~
8. 整理新的项目扫描统计的输出格式 **doing**
9. cmake的命令执行过程中可能会出现自动生成的源文件，这部分要如何处理，需要调研一下(example: blender项目) **doing**
10. 项目执行入口需要完善，main.sh
11. ~~automake项目的方案解决 **close**~~
12. ~~Makefile直接构建项目的解决 **delay**~~
13. 数据导出模块需要修改一下 **doing**
14. ~~automake项目的输出结果如何与cmake，makefile项目兼容，需要设计一下~~
15. ~~automake项目和Makefile项目统一做成make -Bnkw的方式， cmake可以暂时保留这种方式~~
16. ~~另外扫描目录的逻辑需要保留并与make -Bnkw的进行结合~~
17. ~~gcc命令解析需要重新完善一下~~
18. 

### 依赖模块
* 这里依赖了[redis](https://pypi.python.org/pypi/redis/2.10.6)模块，如果有该模块的则可以直接使用，否则需要去git clone https://github.com/andymccurdy/redis-py 项目下来，并将redis目录放到utils目录下，这样项目就能引入该模块来使用 \
之所以这么麻烦是当心之后可能需要对redis client进行精简
* make -Bnkw的方式获取的命令解析参考了[compiledb-generator](https://github.com/nickdiego/compiledb-generator)
