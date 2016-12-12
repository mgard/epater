import traceback
import asyncio
import json

import websockets

from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter
from procsimulator import Simulator, Register


interpreters = {}
connected = set()


async def producer(data_list):
    # Simuler des interruptions externes
    while True:
        if data_list:
            return json.dumps(data_list.pop(0))
        await asyncio.sleep(0.1)


async def handler(websocket, path):
    print("User {} connected.".format(websocket))
    connected.add(websocket)
    to_send = []
    received = []
    try:
        while True:
            if not websocket.open:
                break
            listener_task = asyncio.ensure_future(websocket.recv())
            producer_task = asyncio.ensure_future(producer(to_send))
            done, pending = await asyncio.wait(
                [listener_task, producer_task],
                #timeout=0.001,
                return_when=asyncio.FIRST_COMPLETED)

            if listener_task in done:
                try:
                    message = listener_task.result()
                except websockets.exceptions.ConnectionClosed:
                    break
                if message:
                    received.append(message)

                # TODO: Try là-dessus?
                data = process(websocket, received)
                if data:
                    to_send.extend(data)
            else:
                listener_task.cancel()

            if producer_task in done:
                message = producer_task.result()
                await websocket.send(message)
            else:
                producer_task.cancel()

            # Continue executions of "run", "step out" and "step forward"1
            # TODO: This won't scale
            if not done:
                print("Here!")
                for ws, interp in interpreters.items():
                    if not interp.shouldStop:
                        interp.step()
                        print("RUNNING!")
                        to_send.extend(updateDisplay(interp))

    finally:
        if websocket in interpreters:
            del interpreters[websocket]
        connected.remove(websocket)
        print("User {} disconnected.".format(websocket))


def generateUpdate(inter):
    """
    Generates the messages to update the interface
    """
    retval = []

    # Breakpoints
    #retval.extend(tuple({k.lower(): v.breakpoint for k,v in inter.getRegisters().items()}.items()))
    bpm = inter.getBreakpointsMem()
    retval.extend([["membp_r", bpm['r']],
                   ["membp_w", bpm['w']],
                   ["membp_rw", bpm['rw']],
                   ["membp_e", bpm['e']]])

    # Memory View
    mem = inter.getMemory()
    mem_addrs = range(0, len(mem), 16)
    chunks = [mem[x:x+16] for x in mem_addrs]
    vallist = []
    for i, line in enumerate(chunks):
        cols = {"c{}".format(j): "{:02x}".format(char).upper() for j, char in enumerate(line)}
        cols["ch"] = "0x{:08x}".format(mem_addrs[i])
        # web interface is 1-indexed in this case
        vallist.append({"id": i + 1, "values": cols})
    retval.append(["mem", vallist])

    # Registers
    registers_types = inter.getRegisters()
    retval.extend(tuple({k.lower(): "{:08x}".format(v) for k,v in registers_types['User'].items()}.items()))
    retval.extend(tuple({"FIQ_{}".format(k.lower()): "{:08x}".format(v) for k,v in registers_types['FIQ'].items()}.items()))
    retval.extend(tuple({"IRQ_{}".format(k.lower()): "{:08x}".format(v) for k,v in registers_types['IRQ'].items()}.items()))
    retval.extend(tuple({"SVC_{}".format(k.lower()): "{:08x}".format(v) for k,v in registers_types['SVC'].items()}.items()))

    flags = inter.getFlags()
    retval.extend(tuple({k.lower(): "{}".format(v) for k,v in flags.items()}.items()))
    if 'SN' not in flags:
        flags = ("sn", "sz", "sc", "sv", "si", "sf")
        retval.extend([["disable", f] for f in flags])

    return retval


def updateDisplay(interp, force_all=False):
    print("IMPLEMENT getChanges()!")
    force_all = True
    retval = []
    if force_all:
        try:
            retval.append(["debugline", interp.getCurrentLine()])
        except AssertionError:
            retval.append(["debugline", -1])

        try:
            retval.append(["debuginstrmem", "0x{:08x}".format(interp.getCurrentInstructionAddress())])
        except Exception as e:
            retval.append(["debuginstrmem", -1])
            retval.append(["error", str(e)])

        retval.extend(generateUpdate(interp))
    else:
        retval = interp.getChanges()

    retval.append(["banking", interp.getProcessorMode()])

    # TODO: check currentBreakpoint if == 8, ça veut dire qu'on est à l'extérieur de la mémoire exécutable.
    if interp.currentBreakpoint:
        if interp.currentBreakpoint.source == 'memory' and bool(interp.currentBreakpoint.mode & 8):
            retval.append(["error", "PC est &agrave; l'ext&eacute;rieur de la m&eacute;moire initialis&eacute;e."])
    return retval


def process(ws, msg_in):
    """
    Output: List of messages to send.
    """
    force_update_all = False
    retval = []
    try:
        for msg in msg_in:
            data = json.loads(msg)
            if data[0] == 'assemble':
                # TODO: Afficher les erreurs à l'écran "codeerror"
                bytecode, bcinfos = ASMparser(data[1].split("\n"))
                interpreters[ws] = BCInterpreter(bytecode, bcinfos)
                force_update_all = True
            elif data[0] == 'stepinto':
                interpreters[ws].step()
            elif data[0] == 'stepforward':
                interpreters[ws].step('forward')
            elif data[0] == 'stepout':
                interpreters[ws].step('out')
            elif data[0] == 'run':
                interpreters[ws].step('run')
            elif data[0] == 'reset':
                interpreters[ws].reset()
            elif data[0] == 'breakpointsinstr':
                interpreters[ws].setBreakpointInstr(data[1])
            elif data[0] == 'breakpointsmem':
                interpreters[ws].toggleBreakpointMem(data[1], data[2])
            elif data[0] == 'update':
                if data[1][0].upper() == 'R':
                    reg_id = int(data[1][1:])
                    interpreters[ws].setRegisters({reg_id: int(data[2], 16)})
                elif data[1].upper() in ('N', 'Z', 'C', 'V', 'I', 'F', 'SN', 'SZ', 'SC', 'SV', 'SI', 'SF'):
                    flag_id = data[1].upper()
                    val = not interpreters[ws].getFlags()[flag_id]
                    interpreters[ws].setFlags({flag_id: val})
                elif data[1][:2].upper() == 'BP':
                    _, mode, reg_id = data[1].split('_')
                    reg_id = int(reg_id[1:])
                    # reg name, mode [r,w,rw]
                    interpreters[ws].setBreakpointRegister(reg_id, mode)
                elif data[1].upper() == 'INTERRUPT_ACTIVE':
                    print('INTERRUPT_ACTIVE')
                    print(data)
                elif data[1].upper() == 'INTERRUPT_CYCLES':
                    print("cycles")
                elif data[1].upper() == 'INTERRUPT_CYCLES_FIRST':
                    print("cycles first")
                elif data[1].upper() == 'INTERRUPT_ID':
                    print("interrupt id")
            elif data[0] == 'memchange':
                val = bytearray([int(data[2], 16)])
                interpreters[ws].setMemory(data[1], val)
            else:
                print("<{}> Unknown message: {}".format(ws, data))
    except Exception as e:
        traceback.print_exc()
        retval.append(["error", str(e)])

    del msg_in[:]

    if ws in interpreters:
        retval.extend(updateDisplay(interpreters[ws], force_update_all))
    return retval


if __name__ == '__main__':
    start_server = websockets.serve(handler, '127.0.0.1', 31415)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
