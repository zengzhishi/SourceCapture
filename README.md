# Rebuild compile unit

### 阶段目标
不读取 .h 和 .c 文件构建一份编译命令脚本，使得gcc -c命令能够全部正确执行，生成对应的.o文件

### TODO list
1. 日志模块的完善
2. building_process模块目前还需要重复写很多地方，需要再抽象
3. source_detective.py过于臃肿，需要分离很多东西，将该模块还原会原来定义的文件识别扫描功能
4. cfg文件定义的日志模板需要优化一下

### 依赖模块
这里依赖了[redis](https://pypi.python.org/pypi/redis/2.10.6)模块，如果有该模块的则可以直接使用，否则需要去git clone https://github.com/andymccurdy/redis-py 项目下来，并将redis目录放到utils目录下，这样项目就能引入该模块来使用 \
之所以这么麻烦是当心之后可能需要对redis client进行精简
