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
    prevbaud = int(arg[0])
    prevind = baudlist[prevbaud]
    id = int(arg[1])
    newbaud = int(arg[2])
    newind = baudlist[newbaud]
    pmx = PMXProtocol(dev, newbaud)
  except:
    print(' ERR: There is some problem.')
  else:
    if pmx.MemREAD8(id, 0) == None:
      pmx.baudrate = prevbaud
      if pmx.MotorWRITE(id, pmx.MOTW_OPT_FREE, ()) != None:
        s = (id, newind, pmx.SYSW_PARITY_NONE, 20)
        if pmx.SystemWRITE(id, s):
          print(' OK')
        else:
          print(' NG')
      else:
        print(f' ERR: Device with ID:{id} not found with BAUDRATE:{prevbaud}')
    else:
      print(' ERR: Competing.')
else:
  print(' usage: changebaud [line] <baudrate> <id> <new baudrate>')
