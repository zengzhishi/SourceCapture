# !/bin/env python
# -*- coding: utf-8 -*_

import macros_analysis


ma = macros_analysis.MacrosAnalyzer("/home/zengzhishi/pinpoint-demo/mosquitto/src/logging.c")
ma.building_macros()
ma.dump_macros()
