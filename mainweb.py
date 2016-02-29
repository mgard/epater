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
                return_when=asyncio.FIRST_COMPLETED)

            if listener_task in done:
                try:
                    message = listener_task.result()
                except websockets.exceptions.ConnectionClosed:
                    break
                if message:
                    received.append(message)
            else:
                listener_task.cancel()

            if producer_task in done:
                message = producer_task.result()
                await websocket.send(message)
            else:
                producer_task.cancel()

            # TODO: Try là-dessus?
            data = process(websocket, received)
            if data:
                to_send.extend(data)
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
    regs = inter.getRegisters()
    retval.extend(zip(list("r{}".format(i) for i in range(16)),
                      list("{:08x}".format(i).upper() for i in regs)))
    return retval


def process(ws, msg_in):
    """
    Output: List of messages to send.
    """
    retval = []
    for msg in msg_in:
        data = json.loads(msg)
        if data[0] == 'assemble':
            # TODO: Afficher les erreurs à l'écran "codeerror"
            bytecode, bcinfos = ASMparser(data[1].split("\n"))
            interpreters[ws] = BCInterpreter(bytecode, bcinfos)

            retval.append(["debugline", interpreters[ws].getCurrentLine()])
            retval.extend(generateUpdate(interpreters[ws]))
        elif data[0] == 'stepinto':
            interpreters[ws].stepinto()
            retval.append(["debugline", interpreters[ws].getCurrentLine()])
            retval.extend(generateUpdate(interpreters[ws]))
        elif data[0] == 'stepforward':
            print("stepforward")
            interpreters[ws].stepforward()
            retval.append(["debugline", interpreters[ws].getCurrentLine()])
            retval.extend(generateUpdate(interpreters[ws]))
        elif data[0] == 'stepout':
            interpreters[ws].stepout()
            retval.append(["debugline", interpreters[ws].getCurrentLine()])
            retval.extend(generateUpdate(interpreters[ws]))
        elif data[0] == 'reset':
            interpreters[ws].reset()
            retval.append(["debugline", interpreters[ws].getCurrentLine()])
            retval.extend(generateUpdate(interpreters[ws]))
        elif data[0] == 'breakpointsinst':
            interpreters[ws].setBreakpoints(data[1])
        elif data[0] == 'breakpointsmem':
            interpreters[ws].setBreakpointsMem(data[1])
        elif data[0] == 'run':
            pass
        elif data[0] == 'animate':
            # Faire step into à chaque intervalle
            pass
        elif data[0] == 'update':
            if data[1][0].upper() == 'R':
                reg_id = int(data[1][1:])
                interpreters[ws].sim.regs[reg_id].set(int(data[2], 16))
            retval.extend(generateUpdate(interpreters[ws]))
        elif data[0] == 'breakpoints':
            pass
        elif data[0] == 'memchange':
            val = bytearray([int(data[2], 16)])
            interpreters[ws].sim.mem.set(data[1], val)
            retval.extend(generateUpdate(interpreters[ws]))
        else:
            print("<{}> Unknown message: {}".format(ws, data))
    del msg_in[:]
    return retval


if __name__ == '__main__':
    start_server = websockets.serve(handler, '127.0.0.1', 31415)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
