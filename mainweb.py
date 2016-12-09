import argparse
import time
import math
import asyncio
import json
import collections
from itertools import repeat

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
            print(done, pending)

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
            if not done:
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
    # Memory View
    mem = inter.getMemory()
    chunks = [mem[x:x+10] for x in range(0, len(mem), 10)]
    vallist = []
    for i, line in enumerate(chunks):
        cols = {"c{}".format(j): "{:02x}".format(char).upper() for j, char in enumerate(line)}
        # web interface is 1-indexed in this case
        vallist.append({"id": i + 1, "values": cols})
    retval.append(["mem", vallist])

    # Registers
    retval.extend(tuple({k.lower(): "{:08x}".format(v) for k,v in inter.getRegisters().items()}.items()))
    retval.extend(tuple({k.lower(): "{}".format(v) for k,v in inter.getFlags().items()}.items()))
    print(retval)
    return retval


def updateDisplay(interp, force_all=False):
    # TODO: Update only required (MAG a dit que ca serait simple)
    force_all = True # TODO: TEMPORAIRE
    if force_all:
        retval = [["debugline", interp.getCurrentLine()],]
        retval.extend(generateUpdate(interp))
    else:
        retval = interp.getChanges()
    return retval


def process(ws, msg_in):
    """
    Output: List of messages to send.
    """
    force_update_all = False
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
            interpreters[ws].step(data[1])
        elif data[0] == 'reset':
            interpreters[ws].reset()
        elif data[0] == 'breakpointsinst':
            interpreters[ws].setBreakpointInstr(data[1])
        elif data[0] == 'breakpointsmem':
            # addr, mode [r,w,rw]
            interpreters[ws].setBreakpointMem(data[1], data[2])
        elif data[0] == 'breakpointsregister':
            # reg name, mode [r,w,rw]
            interpreters[ws].setBreakpointRegister(data[1], data[2])
        elif data[0] == 'update':
            if data[1][0].upper() == 'R':
                reg_id = int(data[1][1:])
                interpreters[ws].setRegisters({reg_id: int(data[2], 16)})
            elif data[1].upper() in ('N', 'Z', 'C', 'V'):
                interpreters[ws].setFlags({data[1]: int(data[2], 16)})
            elif data[1].upper() == 'INTERRUPT_CYCLES':
                pass
            elif data[1].upper() == 'INTERRUPT_ID':
                pass
            retval.extend(generateUpdate(interpreters[ws]))
        elif data[0] == 'memchange':
            val = bytearray([int(data[2], 16)])
            interpreters[ws].sim.mem.set(data[1], val, 1)
            retval.extend(generateUpdate(interpreters[ws]))
        else:
            print("<{}> Unknown message: {}".format(ws, data))
    del msg_in[:]
    if ws in interpreters:
        return updateDisplay(interpreters[ws], force_update_all)
    return []


if __name__ == '__main__':
    start_server = websockets.serve(handler, '127.0.0.1', 31415)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
