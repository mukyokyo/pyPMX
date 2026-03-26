## Overview
A class that communicates with KONDO PMX using only generic libraries.
## Requirement
- Python
- pyserial
## Usage
This section assumes the use of the PMX protocol.

You must instantiate the class with an arbitrary port or socket as an argument. You should specify the `timeoutoffset` as appropriate when latency from the interface or operating system is a factor.
``` python
from pyPMX import PMXProtocol

with PMXProtocol('/dev/ttyAMA0', 57600, timeoutoffset=0.2) as pmx:
```
You can also specify a socket when instantiating the object. This is intended for use with wireless modules that utilize Wi-Fi.
``` python
from pyPMX import PMXProtocol
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
sock.connect((socket.gethostbyname('10.0.0.1'), 5050))

with PMXProtocol(sock, 57600, timeoutoffset=0.4, protocoltype=2) as pmx:
```
PMX is designed to access the memory map by specifying an ID, address, and byte size.<br>
To read 2 bytes of data from address 300 of the PMX with ID=0, do the following. If successful, the data read is returned as a `bytes` type.
``` python
  r = pmx.MemREAD(0, 300, 2)
  print(r)
```
To write data to 3 bytes starting at address 500 of the PMX with ID=0, do the following. The return value is a boolean indicating success or failure.
``` python
  r = pmx.MemWRITE(1, 500, bytes((2, 1, 0)))
  print(r)
```
When reading from or writing to 8/16/32 bit data, it is convenient to use functions with 8/16/32 appended to their names. If you specify `length`, you can handle contiguous data with the same bit size; if you need signed values, simply set `signed=True`.
``` python
  led = pmx.MemREAD8(1, 533)
  if led is not None:
    pmx.MemWRITE8(0, 533, led ^ 1)

  tval = pmx.MemREAD16(1, 700, length=2, signed=True)
  if tval is not None:
    pmx.MemWRITE16(1, 700, tval)
```
Functions like `MotorWRITE` and `SystemREAD` can be a bit tricky to use, so please refer to the sample code.

## Licence

[MIT](https://github.com/mukyokyo/pyPMX/blob/main/LICENSE)
