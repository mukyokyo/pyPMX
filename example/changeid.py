#!/usr/bin/python3
import os, sys
from pyPMX import PMXProtocol

baudlist = { 57600 : 0, 115200 : 1, 625000 : 2, 1000000 : 3, 1250000 : 4, 1500000 : 5, 2000000 : 6, 3000000 : 7 }

if len(sys.argv) == 4:
  arg = sys.argv[1:]
  dev = '\\\\.\\COM10'
elif len(sys.argv) == 5:
  arg = sys.argv[2:]
  dev = sys.argv[1]
else:
  arg = []
  dev = ''

if not os.path.exists(dev):
  dev = ''

if dev != '':
  try:
    baud = int(arg[0])
    baudind = baudlist[baud]
    previd = int(arg[1])
    newid = int(arg[2])
    pmx = PMXProtocol(dev, baud)
  except:
    print(' ERR:There is some problem.')
  else:
    if newid >= 0 and newid <= 239:
      if pmx.MemREAD8(newid, 0) == None:
        s = (newid, baudind, pmx.SYSW_PARITY_NONE, 20)
        if pmx.MotorWRITE(previd, pmx.MOTW_OPT_FREE, ()) != None:
          if pmx.SystemWRITE(previd, s):
            print(' OK')
          else:
            print(' NG')
        else:
          print(f' ERR: Device with ID:{previd} not found with BAUDRATE:{baud}')
      else:
        print(' ERR:Competing.')
    else:
      print(' ERR:There is some problem.')
else:
  print(' usage: changeid [line] <baudrate> <prev id> <new id>')
