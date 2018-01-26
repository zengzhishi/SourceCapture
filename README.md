# Rebuild compile unit

### 阶段目标
不读取 .h 和 .c 文件构建一份编译命令脚本，使得gcc -c命令能够全部正确执行，生成对应的.o文件

### redis
这里依赖了[redis](https://pypi.python.org/pypi/redis/2.10.6)模块，如果有该模块的则可以直接使用，否则需要去git clone https://github.com/andymccurdy/redis-py 项目下来，并将redis目录放到utils目录下，这样项目就能引入该模块来使用 \
之所以这么麻烦是当心之后可能需要对redis client进行精简
