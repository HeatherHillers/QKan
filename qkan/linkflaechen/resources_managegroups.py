# -*- coding: utf-8 -*-

# Resource object code
#
# Created: Fr 29. Sep 11:49:57 2017
#      by: The Resource Compiler for PyQt (Qt v4.8.5)
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore

qt_resource_data = "\
\x00\x00\x00\x92\
\x89\
\x50\x4e\x47\x0d\x0a\x1a\x0a\x00\x00\x00\x0d\x49\x48\x44\x52\x00\
\x00\x00\x17\x00\x00\x00\x18\x08\x02\x00\x00\x00\x9e\x1e\xf1\x22\
\x00\x00\x00\x06\x74\x52\x4e\x53\x00\x00\x00\x00\x00\x00\x6e\xa6\
\x07\x91\x00\x00\x00\x09\x70\x48\x59\x73\x00\x00\x0b\x13\x00\x00\
\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x32\x49\x44\x41\x54\x38\
\x8d\x63\x60\x18\x05\x84\x41\x43\x03\x43\x43\x03\x19\xfa\x98\xa8\
\xed\x10\x0a\x00\x23\x76\x61\x62\xfc\x45\x96\xdf\xf1\x81\x51\xb7\
\xd0\x0f\x8c\xa6\x5d\xea\x82\xc1\xe4\x96\xe1\x07\x00\xdd\x19\x0e\
\x0a\x15\x3b\xb3\xbd\x00\x00\x00\x00\x49\x45\x4e\x44\xae\x42\x60\
\x82\
"

qt_resource_name = "\
\x00\x07\
\x07\x3b\xe0\xb3\
\x00\x70\
\x00\x6c\x00\x75\x00\x67\x00\x69\x00\x6e\x00\x73\
\x00\x13\
\x0f\x09\xa5\x7e\
\x00\x46\
\x00\x6c\x00\x61\x00\x65\x00\x63\x00\x68\x00\x65\x00\x6e\x00\x7a\x00\x75\x00\x6f\x00\x72\x00\x64\x00\x6e\x00\x75\x00\x6e\x00\x67\
\x00\x65\x00\x6e\
\x00\x15\
\x0a\xda\x29\xa7\
\x00\x69\
\x00\x63\x00\x6f\x00\x6e\x00\x5f\x00\x6d\x00\x61\x00\x6e\x00\x61\x00\x67\x00\x65\x00\x67\x00\x72\x00\x6f\x00\x75\x00\x70\x00\x73\
\x00\x2e\x00\x70\x00\x6e\x00\x67\
"

qt_resource_struct = "\
\x00\x00\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x01\
\x00\x00\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x02\
\x00\x00\x00\x14\x00\x02\x00\x00\x00\x01\x00\x00\x00\x03\
\x00\x00\x00\x40\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\
"

def qInitResources():
    QtCore.qRegisterResourceData(0x01, qt_resource_struct, qt_resource_name, qt_resource_data)

def qCleanupResources():
    QtCore.qUnregisterResourceData(0x01, qt_resource_struct, qt_resource_name, qt_resource_data)

qInitResources()
