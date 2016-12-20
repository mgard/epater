import traceback
import string
import time
import random
import asyncio
import json
import os
import sys
from collections import OrderedDict
from multiprocessing import Process

import websockets
from bs4 import BeautifulSoup
from gevent import monkey; monkey.patch_all()
import bottle
from bottle import route, get, template, static_file, request

from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter
from procsimulator import Simulator, Register


UPDATE_THROTTLE_SEC = 0.2

interpreters = {}
connected = set()


DEBUG = 'DEBUG' in sys.argv


async def producer(data_list):
    while True:
        if data_list:
            return json.dumps(data_list.pop(0))
        await asyncio.sleep(0.05)


async def run_instance(websocket):
    while True:
        if websocket in interpreters:
            interp = interpreters[websocket]
            if (not interp.shouldStop) and (time.time() > interp.last_step__ + interp.animate_speed__) and (interp.user_asked_stop__ == False):
                return
        await asyncio.sleep(0.05)


async def update_ui(ws, to_send):
    while True:
        if ws in interpreters:
            interp = interpreters[ws]
            if (interp.next_report__ < time.time() and len(to_send) < 10 and interp.num_exec__ > 0):
                return
        await asyncio.sleep(0.02)


async def handler(websocket, path):
    print("User {} connected.".format(websocket))
    connected.add(websocket)
    to_send = []
    received = []
    ui_update_queue = []
    try:
        listener_task = asyncio.ensure_future(websocket.recv())
        producer_task = asyncio.ensure_future(producer(to_send))
        to_run_task = asyncio.ensure_future(run_instance(websocket))
        update_ui_task = asyncio.ensure_future(update_ui(websocket, to_send))
        while True:
            if not websocket.open:
                break
            done, pending = await asyncio.wait(
                [listener_task, producer_task, to_run_task, update_ui_task],
                return_when=asyncio.FIRST_COMPLETED)

            if listener_task in done:
                try:
                    message = listener_task.result()
                except websockets.exceptions.ConnectionClosed:
                    break
                if message:
                    received.append(message)

                data = process(websocket, received)
                if data:
                    to_send.extend(data)

                listener_task = asyncio.ensure_future(websocket.recv())

            if producer_task in done:
                message = producer_task.result()
                await websocket.send(message)
                producer_task = asyncio.ensure_future(producer(to_send))

            # Continue executions of "run", "step out" and "step forward"
            if to_run_task in done:
                steps_to_do = 50 if interpreters[websocket].animate_speed__ == 0 else 1
                for i in range(steps_to_do):
                    interpreters[websocket].step()
                    interpreters[websocket].last_step__ = time.time()
                    interpreters[websocket].num_exec__ += 1

                    ui_update_queue.extend(updateDisplay(interpreters[websocket]))

                    if interpreters[websocket].shouldStop:
                        break

                to_run_task = asyncio.ensure_future(run_instance(websocket))

            if update_ui_task in done:
                if DEBUG:
                    print("{} in {}".format(interpreters[websocket].num_exec__, time.time() - interpreters[websocket].next_report__ + UPDATE_THROTTLE_SEC))
                interpreters[websocket].num_exec__ = 0

                interpreters[websocket].next_report__ = time.time() + UPDATE_THROTTLE_SEC
                ui_update_dict = OrderedDict()
                mem_update = OrderedDict()
                for el in ui_update_queue:
                    if el[0] == "mempartial":
                        for k,v in el[1]:
                            mem_update[k] = v
                    else:
                        ui_update_dict[el[0]] = el[1:]
                        ui_update_dict.move_to_end(el[0])

                if mem_update:
                    ui_update_dict["mempartial"] = [[[k,v] for k,v in mem_update.items()]]

                for k,v in ui_update_dict.items():
                    to_send.append([k] + v)
                ui_update_queue = []
                update_ui_task = asyncio.ensure_future(update_ui(websocket, to_send))

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
    bpm = inter.getBreakpointsMem()
    retval.extend([["membp_r", ["0x{:08x}".format(x) for x in bpm['r']]],
                   ["membp_w", ["0x{:08x}".format(x) for x in bpm['w']]],
                   ["membp_rw", ["0x{:08x}".format(x) for x in bpm['rw']]],
                   ["membp_e", ["0x{:08x}".format(x) for x in bpm['e']]]])

    # Memory View
    mem = inter.getMemoryFormatted()
    mem_addrs = range(0, len(mem), 16)
    chunks = [mem[x:x+16] for x in mem_addrs]
    vallist = []
    for i, line in enumerate(chunks):
        cols = {"c{}".format(j): char for j, char in enumerate(line)}
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

    # Breakpoints
    retval.append(["asm_breakpoints", inter.getBreakpointInstr()])

    return retval


def updateDisplay(interp, force_all=False):
    retval = []

    try:
        retval.append(["debugline", interp.getCurrentLine()])
    except AssertionError:
        retval.append(["debugline", -1])

    try:
        instr_addr = interp.getCurrentInstructionAddress()
        retval.append(["debuginstrmem", ["0x{:08x}".format(x) for x in range(instr_addr, instr_addr + 4)]])
    except Exception as e:
        retval.append(["debuginstrmem", -1])
        retval.append(["error", str(e)])

    if force_all:
        retval.extend(generateUpdate(interp))
        retval.append(["banking", interp.getProcessorMode()])
    else:
        changed_vals = interp.getChanges()
        if changed_vals:
            if "register" in changed_vals:
                for k,v in changed_vals["register"].items():
                    if k.lower()[-1] in ('v', 'c', 'z', 'n', 'i', 'f'):
                        v = str(bool(v))
                        k = k.lower()
                    else:
                        v = "{:08x}".format(v)
                    k = k.replace("_R", "_r")
                    if k[0] == "R":
                        k = "r" + k[1:]
                    retval.append([k, v])
            if "memory" in changed_vals:
                retval.append(["mempartial", [[k, "{:02x}".format(v).upper()] for k, v in changed_vals["memory"]]])

    diff_bp = interp.getBreakpointInstr(diff=True)
    if diff_bp:
        retval.append(["asm_breakpoints", interp.getBreakpointInstr()])
        bpm = interp.getBreakpointsMem()
        retval.extend([["membp_e", ["0x{:08x}".format(x) for x in bpm['e']]],
                       ["mempartial", []]])

    # TODO: check currentBreakpoint if == 8, ça veut dire qu'on est à l'extérieur de la mémoire exécutable.
    if interp.currentBreakpoint:
        if interp.currentBreakpoint.source == 'memory' and bool(interp.currentBreakpoint.mode & 8):
            retval.append(["error", """Un accès à l'extérieur de la mémoire initialisée a été effectué.
{}""".format(currentBreakpoint.info["desc"])])
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
            if data[0] != 'assemble' and ws not in interpreters:
                raise Exception("Veuillez assembler le code avant d'effectuer cette opération.")
            elif data[0] == 'assemble':
                # TODO: Afficher les erreurs à l'écran "codeerror"
                code = ''.join(s for s in data[1].replace("\t", " ") if s in string.printable)
                bytecode, bcinfos = ASMparser(code.splitlines())
                interpreters[ws] = BCInterpreter(bytecode, bcinfos)
                force_update_all = True
                interpreters[ws].last_step__ = time.time()
                interpreters[ws].next_report__ = 0
                interpreters[ws].animate_speed__ = 0.1
                interpreters[ws].num_exec__ = 0
                interpreters[ws].user_asked_stop__ = False
            elif data[0] == 'stepinto':
                interpreters[ws].step('into')
            elif data[0] == 'stepforward':
                interpreters[ws].step('forward')
                interpreters[ws].user_asked_stop__ = False
                interpreters[ws].last_step__ = time.time()
                interpreters[ws].animate_speed__ = int(data[1]) / 1000
            elif data[0] == 'stepout':
                interpreters[ws].step('out')
                interpreters[ws].user_asked_stop__ = False
                interpreters[ws].last_step__ = time.time()
                interpreters[ws].animate_speed__ = int(data[1]) / 1000
            elif data[0] == 'run':
                if interpreters[ws].shouldStop == False and (interpreters[ws].user_asked_stop__ == False):
                    interpreters[ws].user_asked_stop__ = True
                else:
                    interpreters[ws].user_asked_stop__ = False
                    interpreters[ws].step('run')
                    interpreters[ws].last_step__ = time.time()
                    interpreters[ws].animate_speed__ = int(data[1]) / 1000
            elif data[0] == 'reset':
                interpreters[ws].reset()
            elif data[0] == 'breakpointsinstr':
                interpreters[ws].setBreakpointInstr(data[1])
            elif data[0] == 'breakpointsmem':
                interpreters[ws].toggleBreakpointMem(int(data[1], 16), data[2])
                bpm = interpreters[ws].getBreakpointsMem()
                retval.extend([["membp_r", ["0x{:08x}".format(x) for x in bpm['r']]],
                               ["membp_w", ["0x{:08x}".format(x) for x in bpm['w']]],
                               ["membp_rw", ["0x{:08x}".format(x) for x in bpm['rw']]],
                               ["membp_e", ["0x{:08x}".format(x) for x in bpm['e']]]])
            elif data[0] == 'update':
                if data[1][0].upper() == 'R':
                    reg_id = int(data[1][1:])
                    interpreters[ws].setRegisters({reg_id: int(data[2], 16)})
                elif data[1].upper() in ('N', 'Z', 'C', 'V', 'I', 'F', 'SN', 'SZ', 'SC', 'SV', 'SI', 'SF'):
                    flag_id = data[1].upper()
                    try:
                        val = not interpreters[ws].getFlags()[flag_id]
                    except KeyError:
                        pass
                    interpreters[ws].setFlags({flag_id: val})
                elif data[1][:2].upper() == 'BP':
                    _, mode, reg_id = data[1].split('_')
                    reg_id = int(reg_id[1:])
                    # reg name, mode [r,w,rw]
                    interpreters[ws].setBreakpointRegister(reg_id, mode)
            elif data[0] == "interrupt":
                mode = data[2] # FIQ/IRQ
                interpreters[ws].setInterrupt(mode, not data[1], data[4], data[3], 0)
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


default_code = """SECTION INTVEC

B main

mavariable DC32 0x22,  0x1
monautrevariable DC32 0xFFEEDDCC,  0x11223344

SECTION CODE

main
B testmov

testmov
MOV R0,  #0
MOV R1,  #0xA
MOV R2,  #1, LSL R1
MOV R3,  #0xF0000000
MOV R4,  #0x1000, ASR #3
MOV R5,  PC

testop
MOV R0,  #4
MOV R1,  #0xB
ADD R2,  R0,  R1
SUB R3,  R0,  R1
SUB R4,  R1,  R0
AND R5,  R0,  R1
ORR R6,  R0,  R1
EOR R7,  R6,  R1

testmem
LDR R3,  mavariable
LDR R4,  =mavariable
LDR R10,  [R4,  #8]
SUB R6,  PC,  #8
LDR R7,  =variablemem
STR R6,  [R7]

testloop
MOV R0,  #0
MOV R1,  #0xF
loop ADD R0,  R0,  #1
CMP R0,  R1
BNE loop
BEQ skip
MOV R11,  #0xEF
skip
MOV R2,  #0xFF
MOV R3,  #255
SUBS R4,  R2,  R3
MOVGT R5,  #1
MOVLE R5,  #2
MOVEQ R6,  #3
B main

SECTION DATA

variablemem DS32 10"""

index_template = open('./interface/index.html', 'r').read()
@get('/')
def index():
    if "exercice" in request.query:
        with open(os.path.join("exercices", "{}.html".format(request.query["exercice"])), 'r') as fhdl:
            exercice_html = fhdl.read()
        soup = BeautifulSoup(exercice_html, "html.parser")
        enonce = soup.find("div", {"id": "enonce"})
        code = soup.find("div", {"id": "code"}).text
        if not code:
            code = ""
        if not enonce:
            enonce = ""
    else:
        code = default_code
        enonce = ""
    return template(index_template, code=code, enonce=enonce)


@route('/<filename:path>')
def static_serve(filename):
    return static_file(filename, root='./interface/')


def http_server():
    bottle.run(host='0.0.0.0', port=8000, server="gevent")


if __name__ == '__main__':

    p = Process(target=http_server)
    p.start()

    # Websocket Server
    start_server = websockets.serve(handler, '127.0.0.1', 31415)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

    p.join()