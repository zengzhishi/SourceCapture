# !/bin/env python
# -*- coding: utf-8 -*_
"""

    @FileName: test_building_process.py
    @Author: zengzhishi(zengzs1995@gmail.com)
    @CreatTime: 2018-01-24 15:29:04
    @LastModif: 2018-01-25 15:01:44
    @Note:
"""
import capture.building_process as building_process
import multiprocessing
import time


class CommandBuilder(building_process.ProcessBuilder):
    def mission(self, queue, data, locks=[]):
        """输入一个lock，代表的队列的写锁"""
        lock = locks[0]
        lock.acquire()
        while not queue.empty():
            job = queue.get()
            lock.release()
            result = job[0] + job[1]
            data.append(str(job[0]) + " + " + str(job[1]) + " = " + str(result))
            lock.acquire()
        lock.release()
        #return data

    def run(self, worker_num=building_process.CPU_CORE_COUNT):
        resultlist = self._manager.list()
        self.log_mission("info", "Multiprocess mission Start...")
        start_time = time.clock()

        process_list = []
        for i in range(worker_num):
            p = multiprocessing.Process(target=self.mission, args=(self.queue, resultlist, self.lock,))
            process_list.append(p)
            p.start()

        p = multiprocessing.Process(target=self.log_total_missions, args=(self.queue,))
        process_list.append(p)
        p.start()

        for p in process_list:
            p.join()

        end_time = time.clock()
        self.log_mission("info", "All Process Time: %f" % (end_time - start_time))
        self.log_mission("info", "Multiprocess mission complete...")
        return resultlist


if __name__ == "__main__":
    import random
    data = [(x, int(random.random() * x)) for x in range(500)]

    import logging
    logger = logging.Logger("test")
    formatter = logging.Formatter('%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s', '%a, %d %b %Y %H:%M:%S')
    file_handler = logging.FileHandler("test.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    commandbuilder = CommandBuilder(logger, lock_nums=2)
    commandbuilder.distribute_jobs(data)
    result = commandbuilder.run()

    print(result)

# vi:set tw=0 ts=4 sw=4 nowrap fdm=indent
