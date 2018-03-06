# !/bin/env python
# -*- coding: utf-8 -*_

import rebuild_compile_unit.capture.core.macros_analysis as macros_analysis
import rebuild_compile_unit.capture.source_detective as source_detective
import subprocess
import sys


mode = sys.argv[1]

if mode == '0':
    project_path = sys.argv[2]
    file_path = sys.argv[3]
    sub_folders, files_s, files_h = source_detective.get_present_path(project_path, [])

    ma = macros_analysis.MacrosAnalyzer(file_path, sub_folders)
    ma.start_building_macros()
    definitions_flags = ma.exclude_macros()
    print definitions_flags
    ma.dump_macros()

elif mode == '1':
    project_path = sys.argv[2]
    sub_folders, files_s, files_h = source_detective.get_present_path(project_path, [])
    include_flags = ""
    for sub_folder in sub_folders:
        include_flags += " -I" + sub_folder

    times = 0
    print "file count: %d" % len(files_s)
    for file_s in files_s:
        ma = macros_analysis.MacrosAnalyzer(file_s, sub_folders)
        ma.start_building_macros()
        definitions_flags = ma.exclude_macros()
        output_name = file_s[:-1] + "o"
        command = "gcc -c {} -o {} {} {}".format(file_s, output_name, include_flags, definitions_flags)
        p = subprocess.Popen(command, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, err = p.communicate()

        if p.returncode != 0:
            print " CC Building: {}, fail".format(file_s)
            times += 1

    print "fail times: %d" % times
