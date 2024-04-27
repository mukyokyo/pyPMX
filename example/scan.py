#!/usr/bin/python3
import os, sys
from pyPMX import PMXProtocol

dev = '\\\\.\\COM10' if len(sys.argv) == 1 else sys.argv[1]
if not os.path.exists(dev):
  dev = ''

if dev != '':
  try:
    pmx = PMXProtocol(dev, 57600)
    pmx.FullScan()
  except:
    print(' ERR:There is some problem.')
    pass
  sys.stdout.write('\033[2K\033[1G')
else:
  print(' usage: scan [line]')
