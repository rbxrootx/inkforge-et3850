"""Ghidra headless post-script for the XB22Q5 nwsoc /DOWN/ stream trace.

Run with -postScript ghidra_trace_down_dispatch.py OUTPUT_FILE against an
already imported, analyzed XB22Q5 nwsoc program. This script does not
contact the printer or modify the binary.
"""

from ghidra.app.decompiler import DecompInterface


outpath = getScriptArgs()[0]
fm = currentProgram.getFunctionManager()
mem = currentProgram.getMemory()
dec = DecompInterface()
dec.openProgram(currentProgram)
targets = [0x1571f8, 0x154708, 0x1543d0, 0x15236c,
           0x1528e8, 0xf5b6c, 0xf1d4c, 0xe7c00, 0xe8130]

with open(outpath, 'w') as out:
    out.write('Program: %s\n' % currentProgram.getName())
    for address in [0x1546cc, 0x1546e0]:
        ptr = mem.getInt(toAddr(address)) & 0xffffffff
        out.write('DATA %08x -> %08x %s\n' %
                  (address, ptr, fm.getFunctionContaining(toAddr(ptr))))
    for address in targets:
        fn = fm.getFunctionContaining(toAddr(address))
        out.write('\n===== 0x%x %s =====\n' %
                  (address, fn.getName() if fn else 'MISSING'))
        if fn:
            result = dec.decompileFunction(fn, 120, monitor)
            out.write(result.getDecompiledFunction().getC()
                      if result.decompileCompleted() else result.getErrorMessage())
