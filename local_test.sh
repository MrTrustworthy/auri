#!/usr/bin/env bash

echo "This script is just intended for my local testing, this might not run on your machine :)"

python auri/command_line.py
echo "Trying device activate My Nanoleaf"
python auri/command_line.py device activate "My Nanoleaf"
echo "Trying device list"
python auri/command_line.py device list
echo "Trying on"
python auri/command_line.py on
echo "Trying off"
python auri/command_line.py off
echo "Trying device identify"
python auri/command_line.py device identify
echo "Trying list"
python auri/command_line.py list
echo "Trying play vintage"
python auri/command_line.py play vintage
echo "Trying ambi toggle to start"
python auri/command_line.py ambi
echo "Trying ambi toggle to stop"
python auri/command_line.py ambi
echo "Trying -v -a My Nanoleaf play rain"
python auri/command_line.py -v -a "My Nanoleaf" play rain
