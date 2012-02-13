CPP_CODE_DIR = "cygnome/codeFiles/"
import numpy as np
import os
import sys
from sysconfig import get_config_var

from setuptools import setup
#from Cython.Distutils import build_ext 
#from distutils.core import setup
from distutils.extension import Extension

files = ['MemUtils/MemUtils.cpp', 'Mover/Mover_c.cpp']
files += ['Random/Random_c.cpp', 'WindMover/WindMover_c.cpp']
files += ['CompFunctions.cpp', 'CMyList/CMYLIST.cpp']
files += ['OSSMTimeValue/OSSMTimeValue_c.cpp', 'TimeValue/TimeValue_c.cpp']
files += ['GEOMETRY.cpp']

temp_list = ['cyGNOME/c_gnome.cpp']
for file in files:
    temp_list.append(os.path.join(CPP_CODE_DIR ,file))
files = temp_list

extra_includes=None
compile_args=None
if sys.platform == "darwin":
    macros = [('MAC', 1), ('TARGET_CARBON', 1),]
    if get_config_var('UNIVERSALSDK') != None:
        extra_includes=get_config_var('UNIVERSALSDK')+'/Developer/Headers/FlatCarbon'
    else:
        print 'UNIVERSALSDK not set. aborting.'
        exit(-1)
elif sys.platform == "win32":
	compile_args = ['/W0',]
	macros = [('IBM', 1),]

setup(name='python gnome',
      version='beta', 
      requires=['numpy'],
      #cmdclass={'build_ext': build_ext },
      packages=['gnome','gnome.utilities',],
      ext_modules=[Extension('gnome.c_gnome',
                             files, 
                             language="c++",
			     define_macros = macros,
                             extra_compile_args=compile_args,
			     include_dirs=[CPP_CODE_DIR ,
                                           np.get_include(),
                                           'cyGNOME',
                                           extra_includes,
                                           ],
                             )
                   ]


     )

