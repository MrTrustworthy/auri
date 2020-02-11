#!/usr/bin/env bash

echo "This script is just intended for my local testing, this might not run on your machine :)"

python auri/command_line.py
echo "Trying device activate My Nanoleaf"
python auri/command_line.py device activate "My Nanoleaf"
echo "Trying device list"
python auri/command_line.py device list
echo "Trying device on"
python auri/command_line.py device on
echo "Trying device off"
python auri/command_line.py device off
echo "Trying effects list"
python auri/command_line.py effects list
echo "Trying effects play vint"
python auri/command_line.py effects play vint
echo "Trying effects get name"
python auri/command_line.py effects get name
echo "Trying ambi start"
python auri/command_line.py ambi start
echo "Trying ambi stop"
python auri/command_line.py ambi stop
echo "Trying -v -a My Nanoleaf effects play vint"
python auri/command_line.py -v -a "My Nanoleaf" effects play vint
