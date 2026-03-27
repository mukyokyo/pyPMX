## Usage
When using this, make sure to place `pyPMX.py` in the same directory.

Since “pyPMX.py” also contains code for unit testing, please use that to handle simple tests.<br>
This directory contains scripts for changing IDs and baud rates, as well as for searching for them if you've forgotten them.

Furthermore, I have prepared a script (`pmx.py`) that operates the PMX using the names of parameters assigned in the memory map, without relying on serial communication or dedicated commands. This script defines the pmx class; by instantiating it and associating a single PMX with it, you can utilize its functions. The memory map is generated based on a JSON file located in the `model_data` directory, but you can add parameters via code as needed.<br>
I’ll briefly touch on `pmx.py` below.

Use `pyPMX` to initialize the interface, then pass the instance and the PMX ID to `pmx` to instantiate it.
``` python
from pyDXL import DXLProtocolV2
from pmx import pmx
with PMXProtocol('\\\\.\\COM10', 115200, timeoutoffset=0.1) as pmx_if:
  PMX0 = pmx(pmx_if, 0)
```
After communicating with the ID specified at this point, the information in the internal model is updated. If there is a problem, `PMX0.modelname` will be None, so you can use that to determine whether the operation succeeded or failed.

If successful, the memory map will be assigned as a property of PMX0, so you can simply read and write to it using those names, just as you would with variables.
``` python
  PMX0.TorqueSwitch = 2
  PMX0.ControlMode = 1
  print(f'CtrlMode={bin(PMX0.ControlMode)}')
  PMX0.TorqueSwitch = 1

  PMX0.GoalCommandValue1 = 18000
```
Note that some parameters have coefficient to SI units, which can be accessed by adding the `.phys` suffix as a subproperty. As mentioned earlier, you can also redefine the parameters yourself.
``` python
  PMX0.updateitems({
    'PresentValue': (300, "hhh", "r", (None, None, None), ('º','º/s','mA'), (1 / 100, 1 / 10, 1.0)),
    'GoalPosSpd': (700, 'hh', 'rw', (None, None), ('º', 'º/s'), (1 / 100, 1 / 10)),
  })
  print(PMX0.PresentValue.phys)
  PMX0.GoalPosSpd.phys = 120.0, 50.0
```

Please do give it a try.
