import traceback
import locale
import glob
import string
import time
import random
import asyncio
import json
import os
import sys
import re
import binascii
import base64
from urllib.parse import quote, unquote
from copy import copy
from collections import OrderedDict, defaultdict
from multiprocessing import Process
import smtplib
from email.mime.text import MIMEText

import websockets
from gevent import monkey; monkey.patch_all()
import bottle
from bottle import route, static_file, get, request, template
from bs4 import BeautifulSoup

from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter
from procsimulator import Simulator, Register

with open("emailpass.txt") as fhdl:
    email_password = fhdl.read().strip()


UPDATE_THROTTLE_SEC = 0.3

interpreters = {}
connected = set()


DEBUG = 'DEBUG' in sys.argv


async def producer(ws, data_list):
    while True:
        if ws not in connected:
            break
        if data_list:
            out = []
            while True:
                try:
                    out.append(data_list.pop(0))
                except IndexError:
                    break
            return json.dumps(out)
        await asyncio.sleep(0.05)


async def run_instance(websocket):
    while True:
        if websocket not in connected:
            break
        if websocket in interpreters:
            interp = interpreters[websocket]
            if (not interp.shouldStop) and (time.time() > interp.last_step__ + interp.animate_speed__) and (interp.user_asked_stop__ == False):
                return
        await asyncio.sleep(0.05)


async def update_ui(ws, to_send):
    while True:
        if ws not in connected:
            break
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
        producer_task = asyncio.ensure_future(producer(websocket, to_send))
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
                producer_task = asyncio.ensure_future(producer(websocket, to_send))

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

    except Exception as e:
        ex = traceback.format_exc()
        if not isinstance(e, websockets.exceptions.ConnectionClosed):
            print("Simulator crashed:\n{}".format(ex))
            if not DEBUG:
                try:
                    code = interpreters[websocket].code__
                except (KeyError, AttributeError):
                    code = ""
                try:
                    hist = interpreters[websocket].history__
                except (KeyError, AttributeError):
                    hist = []
                body = """<html><head></head>
    (Simulator crash)
    <h4>Traceback:</h4>
    <pre>{ex}</pre>
    <h4>Code:</h4>
    <pre>{code}</pre>
    <h4>Operation history:</h4>
    <pre>{hist}</pre>
    </html>""".format(code=code, ex=ex, hist="<br/>".join(str(x) for x in hist))
                sendEmail(body)
                print("Email sent!")
    finally:
        if websocket in interpreters:
            del interpreters[websocket]
        connected.remove(websocket)
        print("User {} disconnected.".format(websocket))


def sendEmail(msg):
    msg = MIMEText(msg, 'html')

    msg['Subject'] = "Error happened on ASM Simulator"
    msg['From'] = "simulateurosa@gmail.com"
    msg['To'] = "simulateurosa@gmail.com"

    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login("simulateurosa@gmail.com", email_password)
    s.send_message(msg)
    s.quit()


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
        retval.extend(interp.getCurrentInfos())
    except AssertionError:
        retval.append(["debugline", -1])
        #retval.append(["highlightread", []])
        #retval.append(["highlightwrite", []])
        retval.append(["nextline", -1])
        retval.append(["disassembly", "Information indisponible"])

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
            if "bank" in changed_vals:
                retval.append(["banking", changed_vals["bank"]])

    diff_bp = interp.getBreakpointInstr(diff=True)
    if diff_bp:
        retval.append(["asm_breakpoints", interp.getBreakpointInstr()])
        bpm = interp.getBreakpointsMem()
        retval.extend([["membp_e", ["0x{:08x}".format(x) for x in bpm['e']]],
                       ["mempartial", []]])

    retval.append(["cycles_count", interp.getCycleCount() + 1])

    # Check currentBreakpoint if == 8, ça veut dire qu'on est à l'extérieur de la mémoire exécutable.
    if interp.currentBreakpoint:
        if interp.currentBreakpoint.source == 'memory' and bool(interp.currentBreakpoint.mode & 8):
            retval.append(["error", """Un accès à l'extérieur de la mémoire initialisée a été effectué. {}""".format(interp.currentBreakpoint.infos)])

        elif interp.currentBreakpoint.source == 'assert':
            retval.append(["codeerror", interp.currentBreakpoint.infos[0] + 1, interp.currentBreakpoint.infos[1]])
    return retval


def process(ws, msg_in):
    """
    Output: List of messages to send.
    """
    force_update_all = False
    retval = []
    if ws in interpreters and not hasattr(interpreters[ws], 'history__'):
        interpreters[ws].history__ = []

    try:
        for msg in msg_in:
            data = json.loads(msg)

            if ws in interpreters:
                interpreters[ws].history__.append(data)

            if data[0] != 'assemble' and ws not in interpreters:
                retval.append(["error", "Veuillez assembler le code avant d'effectuer cette opération."])
            elif data[0] == 'assemble':
                # TODO: Afficher les erreurs à l'écran "codeerror"
                code = ''.join(s for s in data[1].replace("\t", " ") if s in string.printable)
                if ws in interpreters:
                    del interpreters[ws]

                bytecode, bcinfos, assertions, errors = ASMparser(code.splitlines())
                if errors:
                    retval.extend(errors)
                else:
                    interpreters[ws] = BCInterpreter(bytecode, bcinfos, assertions)
                    force_update_all = True
                    interpreters[ws].code__ = copy(code)
                    interpreters[ws].last_step__ = time.time()
                    interpreters[ws].next_report__ = 0
                    interpreters[ws].animate_speed__ = 0.1
                    interpreters[ws].num_exec__ = 0
                    interpreters[ws].user_asked_stop__ = False
            elif data[0] == 'stepback':
                interpreters[ws].stepBack()
                force_update_all = True
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
                    _, mode, bank, reg_id = data[1].split('_')
                    reg_id = int(reg_id[1:])
                    # bank, reg name, mode [r,w,rw]
                    interpreters[ws].setBreakpointRegister(bank.lower(), reg_id, mode)
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

        if not DEBUG:
            ex = traceback.format_exc()
            print("Handling loop crashed:\n{}".format(ex))
            try:
                code = interpreters[ws].code__
            except (KeyError, AttributeError):
                code = ""
            try:
                hist = interpreters[ws].history__
            except (KeyError, AttributeError):
                hist = []
            try:
                cmd = msg
            except NameError:
                cmd = ""
            body = """<html><head></head>
(Handling loop crash)
<h4>Traceback:</h4>
<pre>{ex}</pre>
<h4>Code:</h4>
<pre>{code}</pre>
<h4>Operation history:</h4>
<pre>{hist}</pre>
<h4>Current command:</h4>
<pre>{cmd}</pre>
</html>""".format(code=code, ex=ex, hist="<br/>".join(str(x) for x in hist), cmd=cmd)
            sendEmail(body)
            print("Email sent!")

    del msg_in[:]

    if ws in interpreters:
        retval.extend(updateDisplay(interpreters[ws], force_update_all))
    return retval


debug_code = """SECTION INTVEC

B main

mavariable DC32 0x22,  0x1
monautrevariable DC32 0xFFEEDDCC,  0x11223344

SECTION CODE

main
B testmov

testmov
MOV R0,  #0
MOV R1,  #0xA
MOV R2,  R1, LSL #1
MOV R3,  #0xF0000000
MOV R4,  #0x1000
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

default_code = """SECTION INTVEC

B main


SECTION CODE

main


SECTION DATA
"""


def decodeWSGI(data):
    return "".join(chr((0xdc00 if x > 127 else 0) + x) for x in data)


def encodeWSGI(data):
    return bytes([(ord(x) % 0xdc00) for x in data]).decode('utf-8')


def encodeWSGIb(data):
    return bytes([(x % 0xdc00) for x in data]).decode('utf-8')


def encodeWSGIb(data):
    return bytes([(x % 0xdc00) for x in data]).decode('utf-8')


index_template = open('./interface/index.html', 'r').read()
simulator_template = open('./interface/simulateur.html', 'r').read()
@get('/')
def index():
    page = request.query.get("page", "demo")

    code = default_code
    enonce = "<h4>Pas d'&eacute;nonc&eacute;</h4>"
    solution = ""
    title = ""
    sections = {}
    identifier = ""

    if "sim" in request.query:
        this_template = simulator_template
        if request.query["sim"] == "debug":
            code = debug_code

        elif not request.query["sim"] == "nouveau":
            try:
                request.query["sim"] = base64.b64decode(unquote(request.query["sim"]))
                # YAHOG -- When in WSGI, we must add 0xdc00 to every extended (e.g. accentuated) character in order for the 
                # open() call to understand correctly the path
                if locale.getdefaultlocale() == (None, None):
                    request.query["sim"] = decodeWSGI(request.query["sim"])
                    with open(os.path.join("exercices", request.query["sim"]), 'rb') as fhdl:
                        exercice_html = fhdl.read()
                    exercice_html = encodeWSGIb(exercice_html)
                else:
                    request.query["sim"] = request.query["sim"].decode("utf-8")

                    with open(os.path.join("exercices", request.query["sim"]), 'r') as fhdl:
                        exercice_html = fhdl.read()
                soup = BeautifulSoup(exercice_html, "html.parser")
                enonce = soup.find("div", {"id": "enonce"})
                code = soup.find("div", {"id": "code"}).text
                solution = soup.find("div", {"id": "solution"})
                if not code:
                    code = ""
                if not enonce:
                    enonce = ""
                if not solution:
                    solution = ""
            except (FileNotFoundError, binascii.Error):
                pass
    else:
        this_template = index_template
        files = []
        if page in ("demo", "exo", "tp"):
            tomatch = "exercices/{}/*/*.html"
            if page == "tp":
                tomatch = "exercices/{}/*.html"
            files = glob.glob(tomatch.format(page), recursive=True)
            files = [os.sep.join(re.split("\\/", x)[1:]) for x in files]
        sections = OrderedDict()
        for f in sorted(files):
            # YAHOG -- When in WSGI, Python adds 0xdc00 to every extended (e.g. accentuated) character, leading to 
            # errors in utf-8 re-interpretation.
            if locale.getdefaultlocale() == (None, None):
                f = encodeWSGI(f)

            fs = f.split(os.sep)
            if page == "tp":
                k1 = fs[1].replace(".html", "").replace("_", " ").encode('utf-8', 'replace')
                sections[k1] = quote(base64.b64encode(f.encode('utf-8', 'replace')), safe='')
            else:
                k1 = fs[1].replace("_", " ").encode('utf-8', 'replace')
                if k1 not in sections:
                    sections[k1] = OrderedDict()
                sections[k1][fs[2].replace(".html", "").replace("_", " ").encode('utf-8', 'replace')] = quote(base64.b64encode(f.encode('utf-8', 'replace')), safe='')

        if len(sections) == 0:
            sections = {"Aucune section n'est disponible en ce moment.": {}}

        if page == "exo":
            title = "Exercices facultatifs"
        elif page == "tp":
            title = "Travaux pratiques"
        else:
            title = "Démonstrations"

    return template(this_template, code=code, enonce=enonce, solution=solution,
                    page=page, title=title, sections=sections, identifier=identifier,
                    rand=random.randint(0, 2**16))


@route('/static/<filename:path>')
def static_serve(filename):
    return static_file(filename, root='./interface/static/')


def http_server():
    bottle.run(host='0.0.0.0', port=8000, server="gevent")


if __name__ == '__main__':

    if DEBUG:
        p = Process(target=http_server)
        p.start()

    # Websocket Server
    start_server = websockets.serve(handler, '0.0.0.0', 31415)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

    if DEBUG:
        p.join()
