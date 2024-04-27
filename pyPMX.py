#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# pyPMX.py
#
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: (C) 2024 mukyokyo

import serial, threading, array, struct
from typing import Union
from collections import namedtuple
from struct import pack, unpack, iter_unpack

##########################################################
# Functionalized the part of converting int to bytes.
# If specified as a tuple, it is converted to bytes at once.
##########################################################
def B2Bs(d) -> bytes:
  if isinstance(d, list) or isinstance(d, tuple):
    return bytes(((d & 0x7f) | 0x80) if d < 0 else d for d in d)
  else:
    return bytes(pack('<B', ((d & 0x7f) | 0x80) if d < 0 else d))

def W2Bs(d) -> bytes:
  if isinstance(d, list) or isinstance(d, tuple):
    return b''.join([pack('<H',d) for d in [((d & 0x7fff) | 0x8000) if d < 0 else d for d in d]])
  else:
    return bytes(pack('<H', ((d & 0x7fff) | 0x8000) if d < 0 else d))

def L2Bs(d) -> bytes:
  if isinstance(d, list) or isinstance(d, tuple):
    return b''.join([pack('<I',d) for d in [((d & 0x7fffffff) | 0x80000000) if d < 0 else d for d in d]])
  else:
    return bytes(pack('<I', ((d & 0x7fffffff) | 0x80000000) if d < 0 else d))

##########################################################
# API for Kondo PMX
##########################################################
class PMXProtocol:
  BROADCASTING_ID  = 0xff
  CMD_MemREAD      = 0xa0
  CMD_MemWRITE     = 0xa1
  CMD_LOAD         = 0xa2
  CMD_SAVE         = 0xa3
  CMD_MotorREAD    = 0xa4
  CMD_MotorWRITE   = 0xa5
  CMD_SystemREAD   = 0xbb
  CMD_SystemWRITE  = 0xbc
  CMD_ReBoot       = 0xbd
  CMD_FactoryReset = 0xbe
  CMD_SystemINIT   = 0xbf

  (SYSW_BAUD_57600, SYSW_BAUD_115_2k, SYSW_BAUD_625k, SYSW_BAUD_1M, SYSW_BAUD_1_25M, SYSW_BAUD_1_5M, SYSW_BAUD_2M, SYSW_BAUD_3M) = range(8)
  (SYSW_PARITY_NONE, SYSW_PARITY_ODD, SYSW_PARITY_EVEN) = range(3)
  (MOTW_OPT_NONE, MOTW_OPT_TORQUEON, MOTW_OPT_FREE, _, MOTW_OPT_BRAKE, _, _, _, MOTW_OPT_HOLD) = range(9)

  __crc16_lutable = array.array('H')

  def __init__(self, port : Union[serial.Serial, str], baudrate = 57600, timeout = 0.05, lock = None):
    if isinstance(port, serial.Serial):
      self.__serial = port
      self.__baudrate = port.baudrate
      self.__timeout = port.timeout
    else:
      self.__serial = serial.Serial(port, baudrate = baudrate, timeout = timeout)
      self.__baudrate = self.__serial.baudrate
      self.__timeout = self.__serial.timeout

    if lock == None:
      self.__lock = threading.Lock()
    else:
      self.__lock = lock
    self.__status = 0
    poly = 0x1021
    for i in range(256):
      nAccum = i << 8
      for j in range(8):
        nAccum = (poly ^ (nAccum << 1) if nAccum & 0x8000 else nAccum << 1) & 0xffff
      self.__crc16_lutable.append(nAccum)

  def __del__(self):
    del self.__crc16_lutable[:]

  @property
  def lock(self):
    return self.__lock

  @property
  def baudrate(self):
    return self.__serial.baudrate

  @baudrate.setter
  def baudrate(self, baudrate):
    self.__baudrate = baudrate
    self.__serial.baudrate = baudrate

  @property
  def timeout(self):
    return self.__serial.timeout

  @timeout.setter
  def timeout(self, timeout):
    self.__timeout = timeout
    self.__serial.timeout = timeout

  def __reconfig(self):
    self.__serial.baudrate = self.__baudrate
    self.__serial.timeout = self.__timeout

  @property
  def status(self):
    return self.__status

  def __crc16(self, data : bytes) -> int:
    crc = 0
    for d in data:
      crc = (crc << 8) ^ self.__crc16_lutable[((crc >> 8) ^ d) & 0xff]
    return crc & 0xffff

  def TxPacket(self, id : int, cmd : int, opt : int, param : bytes, echo = False) -> (bytes, bool):
    self.__reconfig()
    if ((id >= 0 and id <= 239) or id == self.BROADCASTING_ID) and len(param) <= (256 - 8):
      txp = bytes([0xfe,0xfe,id,len(param) + 8,cmd,opt]) + bytes(param)
      txp += W2Bs(self.__crc16(txp))
      self.__serial.reset_input_buffer()
      if echo: print('TX:', txp.hex(':'))
      self.__serial.write(txp)
      return txp, True
    return None, False

  def __rx(self, length) -> bytes:
    s = self.__serial.read(length)
    l = len(s)
    if l == length:
      return s
    else:
      r = s
      length -= l
      if length > 0:
        while self.__serial.in_waiting > 0:
          s = self.__serial.read(length)
          r += s
          length -= len(s)
          if length <= 0:
            break
      return r

  def RxPacket(self, echo = False) -> (bytes, bool):
    rxp = self.__rx(6)
    if rxp:
      if len(rxp) == 6:
        if rxp[3] > 0:
          l = rxp[3] - 6
          if l > 0:
            rxp += self.__rx(l)
            if len(rxp) == l + 6 and rxp[0] == 0xfe and rxp[1] == 0xfe and unpack('<H', rxp[-2:])[0] == self.__crc16(rxp[:-2]):
              self.__status = rxp[5]
              if echo: print('RX:', rxp.hex(':'))
              return bytes(rxp), True
    if echo: print('RX;', rxp.hex(';'), ' xxx')
    return None, False

  def MemWRITE(self, id : int, addr : int, data : bytes, echo = False) -> bool:
    with self.__lock:
      if ((id >= 0 and id <= 239) or id == self.BROADCASTING_ID) and addr >= 0 and addr <= 0x4ff:
        if self.TxPacket(id, self.CMD_MemWRITE, 1, W2Bs(addr) + data, echo)[1]:
          if id != self.BROADCASTING_ID:
            d, r = self.RxPacket(echo)
            if r:
              return (d[2] == id) and (d[4] == 0x21)
          else:
            return True
      return False

  def MemWRITE8(self, id : int, addr : int, data : Union[int, list, tuple], echo = False) -> bool:
    return self.MemWRITE(id, addr, B2Bs(data), echo)

  def MemWRITE16(self, id : int, addr : int, data : Union[int, list, tuple], echo = False) -> bool:
    return self.MemWRITE(id, addr, W2Bs(data), echo)

  def MemWRITE32(self, id : int, addr : int, data : Union[int, list, tuple], echo = False) -> bool:
    return self.MemWRITE(id, addr, L2Bs(data), echo)

  def MemREAD(self, id : int, addr : int, length : int, echo = False) -> bytes:
    with self.__lock:
      if addr >= 0 and id <= 239 and addr >= 0 and addr <= 0x4ff and length > 0 and length > 0 and length <= 247:
        if self.TxPacket(id, self.CMD_MemREAD, 0, W2Bs(addr) + B2Bs(length), echo)[1]:
          d, r = self.RxPacket(echo)
          if r:
            if d[4] == 0x20 and id == d[2] and (d[5] & (4 + 8 + 0x10 + 0x40)) == 0:
              return bytes(d[6:-2])
      return None

  def MemREAD8(self, id : int, addr : int, length = 1, signed = False, echo = False) -> int:
    r = self.MemREAD(id, addr, length, echo)
    if r != None:
      n = sum(iter_unpack('b' if signed else 'B', r), ())
      return n if length > 1 else n[0]
    return None

  def MemREAD16(self, id : int, addr : int, length = 1, signed = False, echo = False) -> int:
    r = self.MemREAD(id, addr, 2 * length, echo)
    if r != None:
      n = sum(iter_unpack('h' if signed else 'H', r), ())
      return n if length > 1 else n[0]
    return None

  def MemREAD32(self, id : int, addr : int, length = 1, signed = False, echo = False) -> int:
    r = self.MemREAD(id, addr, 4 * length, echo)
    if r != None:
      n = sum(iter_unpack('i' if signed else 'I', r), ())
      return n if length > 1 else n[0]
    return None

  def LOAD(self, id : int, echo = False) -> bool:
    with self.__lock:
      if self.TxPacket(id, self.CMD_LOAD, 0, (), echo)[1]:
        if id != self.BROADCASTING_ID:
          d, r = self.RxPacket(echo)
          if r:
            return id == d[2] and d[4] == 0x22
        else:
          return True;
    return False

  def SAVE(self, id : int, echo = False) -> bool:
    with self.__lock:
      if self.TxPacket(id, self.CMD_SAVE, 0, (), echo)[1]:
        if id != self.BROADCASTING_ID:
          d, r = self.RxPacket(echo)
          if r:
            return id == d[2] and d[4] == 0x23
        else:
          return True;
      return False

  def MotorREAD(self, id : int, echo = False) -> tuple:
    with self.__lock:
      if self.TxPacket(id, self.CMD_MotorREAD, 0, (), echo):
        if id != self.BROADCASTING_ID:
          dat, r = self.RxPacket(echo)
          if r:
            return tuple([dat[6], tuple(n[0] for n in iter_unpack('<h', dat[7:-2])) if len(dat[7:-2]) > 0 and dat[4] == 0x24 else ()])
          else:
            return None
        else:
          return ()
      return None

  def MotorWRITE(self, id : int, opt : int, dat : (), echo = False) -> tuple:
    with self.__lock:
      if self.TxPacket(id, self.CMD_MotorWRITE, opt, W2Bs(dat), echo):
        if id != self.BROADCASTING_ID:
          dat, r = self.RxPacket(echo)
          if r:
            return tuple([dat[6], tuple(n[0] for n in iter_unpack('<h', dat[7:-2])) if len(dat[7:-2]) > 0 and dat[4] == 0x25 else ()])
          else:
            return None
        else:
          return ()
      return None

  def SystemREAD(self, id : int, echo = False) -> tuple:
    with self.__lock:
      if self.TxPacket(id, self.CMD_SystemREAD, 0, (), echo)[1]:
        d, r = self.RxPacket(echo)
        if r:
          if len(d[6:-2]) == 13 and d[4] == 0x3b:
            v = tuple(iter_unpack('<IIIB', d[6:-2]))[0]
            return tuple(v)
      return None

  def SystemWRITE(self, id : int, data : (), echo = False) -> bool:
    if data[0] >= 0 and data[0] <= 239 and data[1] >= 0 and data[1] <= 7 and data[2] >= 0 and data[2] <= 2 and data[3] >= 1 and data[3] <= 255:
      d = self.SystemREAD(id, echo)
      if d:
        with self.__lock:
          if self.TxPacket(id, self.CMD_SystemWRITE, 0xf, L2Bs(d[0]) + B2Bs(data), echo)[1]:
            d, r = self.RxPacket(echo)
            if r:
              return id == d[2] and d[4] == 0x3c and (d[5] & (4 + 8 + 0x10 + 0x20 + 0x40)) == 0
    return False

  def ReBoot(self, id : int, echo = False) -> bool:
    with self.__lock:
      if id != self.BROADCASTING_ID:
        if self.TxPacket(id, self.CMD_ReBoot, 0, W2Bs(0), echo)[1]:
          d, r = self.RxPacket(echo)
          if r:
            return d[2] == id and d[4] == 0x3d
      return False

  def FactoryReset(self, id : int, echo = False) -> bool:
    if id != self.BROADCASTING_ID:
      d = self.SystemREAD(id, echo)
      if d != None:
        with self.__lock:
          if self.TxPacket(id, self.CMD_FactoryReset, 0, L2Bs(d[0]), echo)[1]:
            d, r = self.RxPacket(echo)
            if r:
              return d[2] == id and d[4] == 0x3e
    return False

  def FullScan(self) -> tuple:
    orgtimeout = self.timeout
    orgbaudrate = self.baudrate
    baud=(57600,115200,625000,1000000,1250000,1500000,2000000,3000000)
    self.timeout = 0.005
    for b in baud:
      self.baudrate = b
      for id in range(240):
        r = self.MemREAD8(id, 0)
        print(f'baud:{b:7} id:{id:3} :', end='find\n' if r else 'none\r')
    self.timeout = orgtimeout
    self.baudrate = orgbaudrate

##########################################################
# test code
##########################################################
if __name__ == "__main__":
  import time
  from pyPMX import *

  try:
    pmx = PMXProtocol('\\\\.\\COM10', 3000000)
  except:
    pass
  else:
    ID = 1

    # reboot
    print('ReBoot=', pmx.ReBoot(ID, echo=True))
    time.sleep(0.5)
    '''
    # factory reset
    print('FactoryReset=',pmx.FactoryReset(ID))
    time.sleep(0.5)
    '''
    # load
    print('LOAD=', pmx.LOAD(ID, echo=True))
    # save
    print('SAVE=', pmx.SAVE(ID, echo=True))
    '''
    # sys write
    print('SysWrite=',pmx.SystemWRITE(ID, (ID, pmx.SYSW_BAUD_115_2k, pmx.SYSW_PARITY_NONE, 20)))
    time.sleep(0.5)
    '''
    # sys read
    r = pmx.SystemREAD(ID)
    print('SysRead=', f'${r[0]:08x} ${r[1]:08x} ${r[2]:08x} {r[3]:d} ' if r else 'False')
    # dump memory
    print('dump')
    for addr in range(0, 800, 20):
      r = pmx.MemREAD(ID, addr, 20)
      print(f' MemREAD({addr}:{20})=', r.hex(':') if r else '!!!!!!!!!!!!!!!!!!!!!!!!')
    # gain
    r = pmx.MemREAD(ID, 0, 64)
    print('gain\n MemREAD(0:64)=', *iter_unpack('<IIIIIIIIIIIIIIII', r) if r else '!!!!!!!!')
    # voltage limit
    r = pmx.MemREAD(ID, 76, 8)
    print('volt lim\n MemREAD(76:8)=', *iter_unpack('<HHHH', r) if r else '!!!!!!!!')
    # present value
    r = pmx.MemREAD(ID, 300, 24)
    print('present val\n MemREAD(300:20)=', *iter_unpack('<hhhhhhhhhHHH', r) if r else '!!!!!!!!')
    # error stat
    r = pmx.MemREAD(ID, 400, 6)
    print('err stat\n MemREAD(0:400:7)=', *iter_unpack('<BBBxH', r) if r else '!!!!!!!!')

    print('preparation for pos ctrl')
    # ctrl off

    print(' MotorWRITE=', pmx.MotorWRITE(ID, pmx.MOTW_OPT_FREE, ()))
    time.sleep(0.1)
    # 1:pos,2:speed,4:cur,8:torq,16:pwm,32:time
    print(' MemWRITE8(501)=', pmx.MemWRITE8(ID, 501, 1))
    print(' MemWRITE8(502)=', pmx.MemWRITE8(ID, 502, 0b11111))
    time.sleep(0.1)

    # goal angle
    print('start pos ctrl')
    print(' MotorWRITE=', pmx.MotorWRITE(ID, pmx.MOTW_OPT_TORQUEON, ()))
    for ang in tuple(range(0, 32000, 500)) + tuple(range(32000, -32000, -500)) + tuple(range(-32000, 500, 500)):
      for n in range(10):
        r = pmx.MotorWRITE(ID, pmx.MOTW_OPT_NONE, (ang,))
        if r != None:
          if len(r) > 0:
            print(f' MotorWRITE= {r[0]},', ''.join('{:6},'.format(k) for k in r[1]), 'stat=', pmx.status, end = '\r')
            pmx.MemREAD(ID, 400, 6)
        else:
          pass
          print(' MotorWRITE= !!!!!!!!!!!!!!!!!!!!!!!!')
          break
        time.sleep(0.005)
      else:
        continue
      pass
      break
    else:
      print()
    time.sleep(0.1)
    print(' MotorWRITE=', pmx.MotorWRITE(ID, pmx.MOTW_OPT_FREE, ()))



    print(' MotorWRITE=', pmx.MotorWRITE(ID, pmx.MOTW_OPT_FREE, ()))
    time.sleep(0.1)
    # 1:pos,2:speed,4:cur,8:torq,16:pwm,32:time
    print(' MemWRITE8(501)=', pmx.MemWRITE8(ID, 501, 2))
    time.sleep(0.1)

    # goal angle
    print('start speed ctrl')
    print(' MotorWRITE=', pmx.MotorWRITE(ID, pmx.MOTW_OPT_TORQUEON, ()))
    for spd in tuple(range(0, 2000, 50)) + tuple(range(2000, -2000, -50)) + tuple(range(-2000, 50, 50)):
      for n in range(30):
        r = pmx.MotorWRITE(ID, pmx.MOTW_OPT_NONE, (spd,))
        if r != None:
          if len(r) > 0:
            print(f' MotorWRITE= {r[0]},', ''.join('{:6},'.format(k) for k in r[1]), 'stat=', pmx.status, end = '\r')
            pmx.MemREAD(ID, 400, 6)
        else:
          pass
          print(' MotorWRITE= !!!!!!!!!!!!!!!!!!!!!!!!')
          break
        time.sleep(0.005)
      else:
        continue
      pass
      break
    else:
      print()
    time.sleep(0.1)
    print(' MotorWRITE=', pmx.MotorWRITE(ID, pmx.MOTW_OPT_FREE, ()))

    del pmx

  print('fin')
