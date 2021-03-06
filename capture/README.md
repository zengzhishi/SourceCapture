# Rebuild compile unit

### 阶段目标
不读取 .h 和 .c 文件构建一份编译命令脚本，使得gcc -c命令能够全部正确执行，生成对应的.o文件 \
~~编译命令应当从json和redis中读取来动态构建命令并执行（并行）~~
~~CMake项目基本能扫描完整~~ CMAKE 项目其实可以不用使用项目扫描的方法，同样需要预先执行一次cmake，可以直接通过使用

    
    cmake .. -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

来完成compile_commands.json文件的生成. \
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
19. ~~scons构建工具的调研和集成如capture中 **done**~~
20. ~~命令行输入的设置需要完善，简化 **done**~~
21. ~~suffix, preffix从配置文件读取的功能需要完善 **doing**~~
22. ~~文件更新时间的检查，增量构建，实现make的简化功能，只检查源文件和头文件（是否需要呢？）是否更新 **done**~~ ps: 头文件的检查不读取源文件没法做，不符合现在的项目目标，因此暂时不做头文件的检查
23. link的解析问题，需要开始调研
24. ~~考虑加入更加高级的模式，通过构建宏定义的语法树来生成可能的构建方案，提供给用户这种方式（针对没有任何构建工具的裸代码）~~
25. ~~对于无构建工具的项目，需要分析源码的来获取宏定义，目前存在几个问题: **delay**
    * 数目很多，一个源文件连同其依赖的头文件里面出现的宏，可能有好几百个，不可能直接使用排列组合来完成
    * 一些条件编译里面会引入新的头文件，这部分头文件的存在与否，可能可以作为该宏是否应该被使用的有利依据
    * 条件编译的宏涵盖的代码行数，可能也能作为一个比较有效的优先级评判标准
    * 头文件引用时，有一些是系统头文件的，有一些是项目内的，如何判断区分
    * 宏定义分析时，使用了外部模块PLY，这种依赖于外部模块的部分需要重新改造，获取获取完整的版本下来并入项目中
    ~~ ** 暂时无解 **
26. bazel构建工具的调研和集成 **delay 暂时先不管，不够常见，而且是主要用于java的**
27. ~~自动选择构建方式模式的集成, 采用outer build的方式，尝试执行，逐个测试CMAKE，autotools，scons和make **doing**~~
28. redis 数据库创建和存储的本地化
29. ~~autotools项目的 outer_project 方式配置解析，目前完成了有configure可执行文件的outer_project配置， 但是如果只有configure.ac，Makefile.am文件时，暂时还没办法找到比较有效的outer_project 配置方式，autotools工具基本上都没有提供指定输入路径的方式，只针对当前路径下配置的方式，产生的cache文件也会存储在当前目录. ps: autotools 调用无法做到outer_project~~  **delete**
30. 结果输出目录的管理需要更新, 所有目标文件创建一个新的目录来存储，其他信息文件放在上层，redis放在另一个目录
31. 测试系统的健壮性 **doing**
32. ~~Makefile.am 解析~~
33. ~~configure.ac 解析~~
34. ~~m4 文件的解析~~
35. ~~添加configure.ac依赖变量的保存~~
36. ~~根据原始生成的info_dict，构建curl的源文件编译命令~~
37. ~~调研CMakeLists.txt文件的解析方法，函数定义，以及目标获取的是那些东西等，得出解析方案~~
38. ~~完成CMake项目的解析~~
39. 编译器自带的宏定义，头文件路径获取，将这部分的信息作为clang的编译参数.
40. 调试autotools部分的解析, 最好能改成class的方式
41. 删除部分重复性的东西，整理一下
42. 完善异常捕获机制，保证autotools解析和cmakelist解析部分即使出错也能持续运行



### 依赖模块
* 这里依赖了[redis](https://pypi.python.org/pypi/redis/2.10.6)模块，如果有该模块的则可以直接使用，否则需要去git clone https://github.com/andymccurdy/redis-py 项目下来，并将redis目录放到utils目录下，这样项目就能引入该模块来使用 \
之所以这么麻烦是当心之后可能需要对redis client进行精简
* 解析源文件时，依赖了[PLY](https://pypi.python.org/pypi/ply)，用来完成词法分析，其实也可以简化改造一个自己的出来，不需要依赖外部的
* make -Bnkw的方式获取的命令解析参考了[compiledb-generator](https://github.com/nickdiego/compiledb-generator)
