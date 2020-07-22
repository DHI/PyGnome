#!/bin/sh

# Script to build in develop mode under Anaconda -- requires some lib re-linking!

if [[ "$1" = "" ]] ; then
    echo "usage: ./build_anaconda.sh <build_target> build_target can be 'develop',  'install' or 'cleanall'"
elif [[ "$1" = "develop" ]] ; then
    python setup.py $1 --no-deps
    python re_link_for_anaconda.py
elif [[ "$1" = "install" ]] ; then
    python setup.py $1
    python re_link_for_anaconda.py --nolocalpath
elif [[ "$1" = "cleanall" ]] ; then
    python setup.py $1
else
    echo "unknown target $1"
fi


