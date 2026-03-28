#!/usr/bin/env python3

from pyPMX import PMXProtocol
import warnings, struct, json, os


class pmx:

  BaudrateList = {0: 57600, 1: 115200, 2: 625000, 3: 1000000, 4: 1250000, 5: 1500000, 6: 2000000, 7: 3000000}

  def __del__(self):
    pass

  class WriteError(Exception):
    pass

  class ReadError(Exception):
    pass

  def _build_index(self, config_dir):
    master_config = {}
    for filename in os.listdir(config_dir):
      if filename.endswith('.json'):
        with open(os.path.join(config_dir, filename), 'r', encoding='utf-8', errors='ignore') as f:
          data = json.load(f)
          for key, value in data.items():
            if key == 'models' and key in master_config:
              master_config[key].update(value)
            else:
              master_config[key] = value
    return self._parse_expressions(master_config)

  def _parse_expressions(self, data):
    if isinstance(data, dict):
      return {k: self._parse_expressions(v) for k, v in data.items()}
    elif isinstance(data, list):
      return [self._parse_expressions(i) for i in data]
    elif isinstance(data, str):
      if any(op in data for op in '+*/-') and not any(b in data for b in '[]{}'):
        try:
          return eval(data)
        except:
          return data
    return data

  def _custom_formatwarning(self, message, category, filename, lineno, line=None):
    return f'{category.__name__}: {message}\n'

  def __init__(self, pmx_instance, pmx_id):
    warnings.formatwarning = self._custom_formatwarning
    self._cache = {}
    self._model_index = self._build_index('model_data/')
    self._pmx = pmx_instance
    self._id = pmx_id
    self._sysinfo = self._pmx.SystemREAD(pmx_id)
    if self._sysinfo is not None:
      json_path = self._model_index['models'].get(f'0x{self._sysinfo[1]:08X}')
      if not json_path:
        self._modelname = None
        self._items = {}
        self._firmware_version = None
        raise Exception(f'Model(0x{self._sysinfo[1]:08X}) is not supported.')
      else:
        model_info = self._model_index.get('models').get(f'0x{self._sysinfo[1]:08X}')
        self._modelname = model_info.get('modelname')
        self._firmware_version = self._sysinfo[2]
        self._items = self._model_index.get(model_info.get('controltable')).copy()
        self._items.update(model_info.get('overrides', {}))
    else:
      self._items = {}
      self._modelname = None
      self._firmware_version = None

  def __enter__(self):
    return self

  def __exit__(self, ex_type, ex_value, trace):
    pass

  @property
  def id(self):
    return self._id

  @id.setter
  def id(self, newid):
    if newid >= 0 and newid <= 239 and self._id != newid:
      if self._pmx.MemREAD8(newid, 0) is None:
        if self._pmx.MotorWRITE(self._id, self._pmx.MOTW_OPT_FREE, ()) is not None:
          baudind = [k for k, v in self.BaudrateList.items() if v == self._pmx.baudrate][0]
          s = (newid, baudind, self._pmx.SYSW_PARITY_NONE, self._sysinfo[3])
          if self._pmx.SystemWRITE(self._id, s):
            self._id = newid

  @property
  def baudrate(self):
    return self._pmx.baudrate

  @baudrate.setter
  def baudrate(self, newbaud):
    prevbaud = self._pmx.baudrate
    if newbaud != prevbaud:
      baudind = [k for k, v in self.BaudrateList.items() if v == newbaud]
      if baudind is not None:
        self._pmx.baudrate = newbaud
        if self._pmx.MemREAD8(self._id, 0) is None:
          self._pmx.baudrate = prevbaud
          if self._pmx.MotorWRITE(self._id, self._pmx.MOTW_OPT_FREE, ()) is not None:
            s = (self._id, baudind[0], self._pmx.SYSW_PARITY_NONE, self._sysinfo[3])
            if self._pmx.SystemWRITE(self._id, s):
              self._pmx.baudrate = newbaud
              return
      self._pmx.baudrate = prevbaud

  @property
  def modelname(self):
    return self._modelname

  @property
  def firmwareversion(self):
    if self._firmware_version is not None:
      return tuple(self._firmware_version.to_bytes(4))
    else:
      return None

  @property
  def items(self):
    return self._items

  def updateitems(self, itm):
    self._items.update(itm)

  def dump(self):
    for i in self._items:
      print(f'{self._items[i][0]}:{i}={self.__getattr__(i)}')

  def _genstr(self, val, coef, unit):
    ret = ''
    if isinstance(val, list | tuple):
      for i, _val in enumerate(val):
        if coef is not None and isinstance(coef, list | tuple):
          if coef[i] is not None:
            ret += f'{float(_val) * coef[i]:.3f}'
          else:
            ret += f'{float(_val)}'
        else:
          ret += f'{_val}'
        if unit is not None and unit != '' and isinstance(unit, list | tuple):
          if unit[i] != '':
            ret += f'[{unit[i]}]'
        ret += ', '
      ret = ret.rstrip(', ')
    else:
      if coef is not None:
        ret += f'{float(val) * coef:.3f}'
      else:
        ret += f'{val}'
      if unit is not None and unit != '':
        ret += f'[{unit}]'
    return ret

  def _conv_format_value(self, name, fmt, unit, coef, val):
    p = tuple(struct.iter_unpack('<' + fmt, val))[0]
    if len(p) == 1:
      class conv_physvalue(int):

        @property
        def info(self_val):
          return self._items[name]

        @property
        def phys(self_val):
          return float(self_val) * coef

        @property
        def str(self_val):
          return self._genstr(self_val, coef, unit)

        @phys.setter
        def phys(self_val, val):
          setattr(self, name, int(val / coef))

      return conv_physvalue(p[0])
    else:
      class conv_physvalue(tuple):

        @property
        def info(self_val):
          return self._items[name]

        @property
        def phys(self_val):
          if isinstance(self_val, list | tuple):
            return list(float(x) * (y if y is not None else 1.0) for (x, y) in zip(self_val, coef))
          else:
            return float(self_val) * coef

        @property
        def str(self_val):
          return self._genstr(self_val, coef, unit)

        @phys.setter
        def phys(self_val, val):
          if isinstance(val, list | tuple):
            setattr(self, name, list(int(x / (y if y is not None else 1.0)) for (x, y) in zip(val, coef)))
          else:
            setattr(self, name, int(val / coef))

      return conv_physvalue(p[0] if len(p) == 1 else p)

  def __getattr__(self, name):
    if name in self._items:
      addr, fmt, _, _, unit, coef = self._items[name]
      size = struct.calcsize(fmt)

      if hasattr(self, f"_{name}"):
        return getattr(self, f"_{name}")

      r = self._pmx.MemREAD(self._id, addr, size)
      if r is not None:
        return self._conv_format_value(name, fmt, unit, coef, r)
      else:
        if self._pmx.status == 0:
          warnings.warn('Read operation failed. It appears to be a receve timeout.', UserWarning)
          return None
        else:
          raise self.ReadError(f'Read operation failed. Error code:${self._pmx.status:02X}({self.StatusError.get(self._dx.status & 0x7F, "")})')
    raise AttributeError(f'No such item: {name}')

  def __setattr__(self, name, value):
    if name.startswith('_'):
      self.__dict__[name] = value
      return
    elif name == 'id' or name == 'baudrate':
      super().__setattr__(name, value)
      return

    if name in self._items:
      addr, fmt, access, val_range, _, _ = self._items[name]
      if 'w' not in access:
        raise AttributeError(f'{name} is Read-Only')
      v_min, v_max = val_range
      if v_min is not None and v_max is not None:
        if isinstance(v_min, list | tuple) and isinstance(v_max, list | tuple) and isinstance(value, list | tuple):
          newvalue = list(value)
          for i, (_vmin, _vmax, _v) in enumerate(zip(v_min, v_max, newvalue)):
            if not (_vmin <= _v <= _vmax):
              _nv = min(max(_v, _vmin), _vmax)
              warnings.warn(f'Out of Range: {name} ({_v}) must be {_vmin}~{_vmax}. Clipped at {_nv}', UserWarning)
              newvalue[i] = _nv
          value = list(newvalue)

        elif not (v_min <= value <= v_max):
          newvalue = min(max(value, v_min), v_max)
          warnings.warn(f'Out of Range: {name} ({value}) must be {v_min}~{v_max}. Clipped at {newvalue}', UserWarning)
          value = newvalue
      if isinstance(value, list | tuple):
        wvalue = struct.pack('<' + fmt, *value)
      else:
        wvalue = struct.pack('<' + fmt, value)

      if not self._pmx.MemWRITE(self.id, addr, wvalue):
        if self._pmx.status == 0:
          warnings.warn('Write operation failed. It appears to be a receve timeout.', UserWarning)
        else:
          raise self.WriteError(f'Write operation failed. Error code:${self._dx.status:02X}({self.StatusError.get(self._dx.status & 0x7F, "")})')
    else:
      raise AttributeError(f'No such item: {name}')


if __name__ == '__main__':
  from time import sleep, time
  import traceback, sys, os

  def wait(t):
    end_time = time() + t
    while end_time > time():
      yield

  with PMXProtocol('\\\\.\\COM3', 115200, timeoutoffset=0.3) as pmx_if:
    try:
      # List only the instances of PMX that were found as p
      p = []
      for i in range(10):
        p += pmx(pmx_if, i),
        if p[-1].modelname is not None:
          # Add properties based on the angle and velocity cascade
          p[-1].updateitems({
            'PresentValue': (300, "hhh", "r", (None, None), ('º','º/s','mA'), (1 / 100, 1 / 10, 1.0)),
            'PresentValue2': (300, "Hhh", "r", (None, None), ('º','º/s','mA'), (1 / 100, 1 / 10, 1.0)),
            'GoalPos': (700, 'h', 'rw', (-32000, 32000), 'º', 1 / 100),
            'GoalCur': (700, 'h', 'rw', (-3800, 3800), 'mA', 1.0),
            'GoalPosSpd': (700, 'hh', 'rw', ((-32000, -3800), (32000, 3800)), ('º', 'º/s'), (1 / 100, 1 / 10)),
            'GoalPosSpdCur': (700, 'hhh', 'rw', ((-32000, -4700, -3800), (32000, 4700, 3800)), ('º', 'º/s', 'mA'), (1 / 100, 1 / 10, 1.0)),
            'GoalSpdCur': (700, 'hh', 'rw', ((-3800, -4700), (3800, 4700)), ('º/s', 'mA'), (1 / 10, 1.0)),
          })
          print(p[-1].id, p[-1].modelname, p[-1].firmwareversion)
        else:
          p.pop(-1)
      else:
        print()

      if p == []:
        sys.exit()

      # Although multiple PMXs are listed, for now, only the first one found (p[0]) is being operated.
      p[0].dump()
      input('Waiting for the Enter key to be pressed...')

      # Print some of the maximum values
      print(f'CwPositionLimit={p[0].CwPositionLimit}')
      print(f'MaxGoalSpeed={p[0].MaxGoalSpeed}')
      print(f'MaxGoalCurrent={p[0].MaxGoalCurrent}')

      # Set the control mode (position)
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_FREE
      p[0].ControlMode = 1
      print(f'Control_Mode={bin(p[0].ControlMode)}')
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_TORQUEON
      for i in tuple(range(0, 360, 40)) + tuple(range(360, -360, -40)) + tuple(range(-360, 0, 40)):
        p[0].GoalPos.phys = i
        for _ in wait(0.5):
          print(p[0].GoalPos.phys, p[0].PresentValue.str, p[0].MotorTemp.str, end='\033[K\r')
      else:
        print()

      # Set the control mode (position & speed)
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_FREE
      p[0].ControlMode = 1 | 2
      print(f'Control_Mode={bin(p[0].ControlMode)}')
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_TORQUEON
      for i in tuple(range(0, 360, 80)) + tuple(range(360, -360, -80)) + tuple(range(-360, 0, 80)):
        p[0].GoalPosSpd.phys = i, 100
        for _ in wait(1.0):
          print(p[0].GoalPosSpd.phys, p[0].PresentValue.str, p[0].MotorTemp.str, end='\033[K\r')
      else:
        print()

      # Set the control mode (position & speed & current)
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_FREE
      p[0].ControlMode = 1 | 2 | 4
      print(f'Control_Mode={bin(p[0].ControlMode)}')
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_TORQUEON
      for i in tuple(range(0, 320, 80)) + tuple(range(320, -320, -80)) + tuple(range(-320, 0, 80)):
        p[0].GoalPosSpdCur.phys = i, 100, 160
        for _ in wait(1.0):
          print(p[0].GoalPosSpdCur.phys, p[0].PresentValue.str, p[0].MotorTemp.str, end='\033[K\r')
      else:
        print()

      # Set the control mode (speed & current)
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_FREE
      p[0].ControlMode = 2 | 4
      print(f'Control_Mode={bin(p[0].ControlMode)}')
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_TORQUEON
      for i in tuple(range(0, 400, 25)) + tuple(range(400, -400, -25)) + tuple(range(-400, 0, 25)):
        p[0].GoalSpdCur.phys = i, 500
        for _ in wait(1.0):
          print(p[0].GoalSpdCur.phys, p[0].PresentValue2.str, p[0].MotorTemp.str, end='\033[K\r')
      else:
        print()

      # Set the control mode (current)
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_FREE
      p[0].ControlMode = 4
      print(f'Control_Mode={bin(p[0].ControlMode)}')
      p[0].TorqueSwitch = pmx_if.MOTW_OPT_TORQUEON
      for i in tuple(range(0, 4000, 200)) + tuple(range(4000, -4000, -200)) + tuple(range(-4000, 0, 200)):
        p[0].GoalCur.phys = i
        for _ in wait(0.2):
          print(p[0].GoalCur.phys, p[0].PresentValue2.str, p[0].MotorTemp.str, end='\033[K\r')
      else:
        print()

    except KeyboardInterrupt:
      pass
    except:
      print('--- Caught Exception ---')
      traceback.print_exc()
      print('------------------------')
    finally:
      if p != []:
        sleep(0.3)
        for _p in p:
          _p.TorqueSwitch = 2
