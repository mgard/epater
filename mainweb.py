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
import io
import binascii
import signal
import base64
import i18n
from urllib.parse import quote, unquote
from copy import copy
from collections import OrderedDict, defaultdict
from multiprocessing import Process
import smtplib
from email.mime.text import MIMEText

try:
    import uvloop
except ImportError:
    pass
import websockets
from gevent import monkey; monkey.patch_all()
import bottle
from bottle import route, static_file, get, post, request, template, response
from bottle_i18n import I18NPlugin, I18NMiddleware, i18n_defaults, i18n_view, i18n_template
from bs4 import BeautifulSoup

from assembler import parse as ASMparser
from bytecodeinterpreter import BCInterpreter


with open("emailpass.txt") as fhdl:
    email_password = fhdl.read().strip()

try:
    with open("privepass.txt") as fhdl:
        prive_password = fhdl.read().strip()
except FileNotFoundError:
    prive_password = None


UPDATE_THROTTLE_SEC = 0.3

interpreters = {}
connected = set()


DEBUG = 'DEBUG' in sys.argv

default_lang = 'fr'
i18n_defaults(bottle.SimpleTemplate, bottle.request)
i18NPlugin = I18NPlugin(domain='interface', default=default_lang, locale_dir='./locale')

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
            if (interp.user_asked_stop__ == False) and (time.time() > interp.last_step__ + interp.animate_speed__):
                return
        await asyncio.sleep(0.05)


async def update_ui(ws, to_send):
    while True:
        if ws not in connected:
            break
        if ws in interpreters:
            interp = interpreters[ws]
            if (interp.next_report__ < time.time() and interp.num_exec__ > 0):
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
                timeout=3600, return_when=asyncio.FIRST_COMPLETED)

            if len(done) == 0:
                print("{} timeout!".format(websocket))
                listener_task.cancel()
                producer_task.cancel()
                to_run_task.cancel()
                break

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

            if websocket not in interpreters:
                await asyncio.sleep(0.05)
                continue

            # Continue executions of "run", "step out" and "step forward"
            if to_run_task in done:
                if interpreters[websocket].animate_speed__:
                    interpreters[websocket].step()
                    interpreters[websocket].last_step__ = time.time()
                    interpreters[websocket].num_exec__ += 1
                    if interpreters[websocket].shouldStop:
                        interpreters[websocket].user_asked_stop__ = True
                    ui_update_queue.extend(updateDisplay(interpreters[websocket]))

                else:
                    interpreters[websocket].num_exec__ -= interpreters[websocket].getCycleCount()
                    interpreters[websocket].execute()
                    interpreters[websocket].last_step__ = time.time()
                    interpreters[websocket].num_exec__ += interpreters[websocket].getCycleCount()
                    interpreters[websocket].num_exec__ = max(interpreters[websocket].num_exec__, 1)
                    interpreters[websocket].user_asked_stop__ = True
                    ui_update_queue.extend(updateDisplay(interpreters[websocket]))

                to_run_task = asyncio.ensure_future(run_instance(websocket))


            if update_ui_task in done:
                if DEBUG:
                    print("{} in {}".format(interpreters[websocket].num_exec__, time.time() - interpreters[websocket].next_report__ + UPDATE_THROTTLE_SEC))
                interpreters[websocket].num_exec__ = 0

                interpreters[websocket].next_report__ = time.time() + UPDATE_THROTTLE_SEC

                to_send.extend(ui_update_queue)
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
    retval.extend(tuple({"r{}".format(k): "{:08x}".format(v) for k,v in registers_types['User'].items()}.items()))
    retval.extend(tuple({"FIQ_r{}".format(k): "{:08x}".format(v) for k,v in registers_types['FIQ'].items()}.items()))
    retval.extend(tuple({"IRQ_r{}".format(k): "{:08x}".format(v) for k,v in registers_types['IRQ'].items()}.items()))
    retval.extend(tuple({"SVC_r{}".format(k): "{:08x}".format(v) for k,v in registers_types['SVC'].items()}.items()))

    # Flags
    retval.extend(inter.getFlagsFormatted())

    # Breakpoints
    retval.append(["asm_breakpoints", inter.getBreakpointInstr()])

    # Errors
    retval.extend(inter.getErrorsFormatted())

    return retval


def updateDisplay(interp, force_all=False):
    retval = []

    currentLine = interp.getCurrentLine()
    if currentLine:
        retval.append(["debugline", currentLine])
        retval.extend(interp.getCurrentInfos())
    else:
        retval.append(["debugline", -1])
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
        retval.extend(interp.getChangesFormatted(setCheckpoint=True))

    diff_bp = interp.getBreakpointInstr(diff=True)
    if diff_bp:
        retval.append(["asm_breakpoints", interp.getBreakpointInstr()])
        bpm = interp.getBreakpointsMem()
        retval.extend([["membp_e", ["0x{:08x}".format(x) for x in bpm['e']]],
                       ["mempartial", []]])

    retval.append(["cycles_count", interp.getCycleCount()])

    return translate_retval(interp.lang, retval)


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
                lang = default_lang
                if data[0] != "interrupt":
                    retval.append(["error", "Veuillez assembler le code avant d'effectuer cette opération."])
            elif data[0] == 'assemble':
                lang = data[2]
                code = ''.join(s for s in data[1].replace("\t", " ") if s in string.printable)
                if ws in interpreters:
                    del interpreters[ws]

                bytecode, bcinfos, line2addr, assertions, snippetMode, errors = ASMparser(code.splitlines())
                if errors:
                    retval.extend(errors)
                    retval.append(["edit_mode"])
                else:
                    interpreters[ws] = BCInterpreter(bytecode, bcinfos, assertions, snippetMode=snippetMode)
                    force_update_all = True
                    interpreters[ws].code__ = copy(code)
                    interpreters[ws].last_step__ = time.time()
                    interpreters[ws].next_report__ = 0
                    interpreters[ws].animate_speed__ = 0.1
                    interpreters[ws].num_exec__ = 0
                    interpreters[ws].user_asked_stop__ = True
                    retval.append(["line2addr", line2addr])
                    interpreters[ws].lang = lang
            else:
                lang = interpreters[ws].lang
                if data[0] == 'stepback':
                    interpreters[ws].stepBack()
                    force_update_all = True
                elif data[0] == 'stepinto':
                    interpreters[ws].execute('into')
                elif data[0] == 'stepforward':
                    interpreters[ws].setStepMode('forward')
                    interpreters[ws].user_asked_stop__ = False
                    interpreters[ws].last_step__ = time.time()
                    try:
                        interpreters[ws].animate_speed__ = int(data[1]) / 1000
                    except (ValueError, TypeError):
                        interpreters[ws].animate_speed__ = 0
                        retval.append(["animate_speed", str(interpreters[ws].animate_speed__)])
                elif data[0] == 'stepout':
                    interpreters[ws].setStepMode('out')
                    interpreters[ws].user_asked_stop__ = False
                    interpreters[ws].last_step__ = time.time()
                    try:
                        interpreters[ws].animate_speed__ = int(data[1]) / 1000
                    except (ValueError, TypeError):
                        interpreters[ws].animate_speed__ = 0
                        retval.append(["animate_speed", str(interpreters[ws].animate_speed__)])
                elif data[0] == 'run':
                    if interpreters[ws].shouldStop == False and (interpreters[ws].user_asked_stop__ == False):
                        interpreters[ws].user_asked_stop__ = True
                    else:
                        interpreters[ws].user_asked_stop__ = False
                        interpreters[ws].setStepMode('run')
                        interpreters[ws].last_step__ = time.time()
                        try:
                            anim_speed = int(data[1]) / 1000
                        except (ValueError, TypeError):
                            anim_speed = 0
                            retval.append(["animate_speed", str(anim_speed)])
                        interpreters[ws].animate_speed__ = anim_speed
                elif data[0] == 'stop':
                    del interpreters[ws]
                elif data[0] == 'reset':
                    interpreters[ws].reset()
                elif data[0] == 'breakpointsinstr':
                    interpreters[ws].setBreakpointInstr(data[1])
                    force_update_all = True
                elif data[0] == 'breakpointsmem':
                    try:
                        interpreters[ws].toggleBreakpointMem(int(data[1], 16), data[2])
                    except ValueError:
                        retval.append(["error", "Adresse mémoire invalide"])
                    else:
                        bpm = interpreters[ws].getBreakpointsMem()
                        retval.extend([["membp_r", ["0x{:08x}".format(x) for x in bpm['r']]],
                                       ["membp_w", ["0x{:08x}".format(x) for x in bpm['w']]],
                                       ["membp_rw", ["0x{:08x}".format(x) for x in bpm['rw']]],
                                       ["membp_e", ["0x{:08x}".format(x) for x in bpm['e']]]])
                elif data[0] == 'update':
                    reg_update = re.findall(r'^(?:([A-Z]{3})_)?r(\d{1,2})', data[1])
                    if reg_update:
                        bank, reg_id = reg_update[0]
                        if not len(bank):
                            bank = 'User'
                        try:
                            interpreters[ws].setRegisters(bank, int(reg_id), int(data[2], 16))
                        except (ValueError, TypeError):
                            retval.append(["error", "Valeur invalide: {}".format(repr(data[2]))])
                    elif data[1].upper() in ('N', 'Z', 'C', 'V', 'I', 'F', 'SN', 'SZ', 'SC', 'SV', 'SI', 'SF'):
                        flag_id = data[1].upper()
                        try:
                            val = not interpreters[ws].getFlags()[flag_id]
                        except KeyError:
                            pass
                        else:
                            interpreters[ws].setFlags(flag_id, val)
                    elif data[1][:2].upper() == 'BP':
                        _, mode, bank, reg_id = data[1].split('_')
                        try:
                            reg_id = int(reg_id[1:])
                        except (ValueError, TypeError):
                            retval.append(["error", "Registre invalide: {}".format(repr(reg_id[1:]))])
                        # bank, reg name, mode [r,w,rw]
                        interpreters[ws].setBreakpointRegister(bank.lower(), reg_id, mode)
                    force_update_all = True
                elif data[0] == "interrupt":
                    mode = ["FIQ", "IRQ"][data[2] == "IRQ"] # FIQ/IRQ
                    try: cycles_premier = int(data[4])
                    except (TypeError, ValueError): cycles_premier = 50; retval.append(['interrupt_cycles_first', 50])
                    try: cycles = int(data[3])
                    except (TypeError, ValueError): cycles = 50; retval.append(['interrupt_cycles', 50])
                    try: notactive = bool(data[1])
                    except (TypeError, ValueError): notactive = 0; retval.append(['interrupt_active', 0])
                    interpreters[ws].setInterrupt(mode, not notactive, cycles_premier, cycles, 0)
                elif data[0] == 'memchange':
                    try:
                        val = bytearray([int(data[2], 16)])
                    except (ValueError, TypeError):
                        retval.append(["error", "Valeur invalide: {}".format(repr(data[2]))])
                        val = interpreters[ws].getMemory(data[1])
                        retval.append(["mempartial", [[data[1], val]]])
                    else:
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

    if None == lang:
        lang = interpreters[ws].lang
    retval = translate_retval(lang, retval)

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

fin
B fin

SECTION DATA
"""


def decodeWSGI(data):
    return "".join(chr((0xdc00 if x > 127 else 0) + x) for x in data)


def encodeWSGI(data):
    return bytes([(ord(x) % 0xdc00) for x in data]).decode('utf-8')


def encodeWSGIb(data):
    return bytes([(x % 0xdc00) for x in data]).decode('utf-8')


def readFileBrokenEncoding(filename):
    if locale.getdefaultlocale() == (None, None):
        with open(filename, 'rb') as fhdl:
            data = fhdl.read()
        data = encodeWSGIb(data)
    else:
        with io.open(filename, 'r', encoding="utf-8") as fhdl:
            data = fhdl.read()
    return data


if locale.getdefaultlocale() == (None, None):
    index_template = open('./interface/index.html', 'rb').read()
    simulator_template = open('./interface/simulateur.html', 'rb').read()
    index_template = encodeWSGIb(index_template)
    simulator_template = encodeWSGIb(simulator_template)
else:
    index_template = open('./interface/index.html', 'r').read()
    simulator_template = open('./interface/simulateur.html', 'r').read()

def get():
    app = bottle.Bottle()

    @app.route('/')
    def index():
        page = request.query.get("page", "accueil")

        code = default_code
        enonce = ""
        solution = ""
        title = ""
        sections = {}
        identifier = ""
        extra_left = ""

        is_private_session = False
        if prive_password is not None:
            getval = request.query.get("prive", None)
            if getval is not None:
                is_private_session = getval == prive_password
                response.set_cookie("prive", request.query.get("prive", None))
            else:
                is_private_session = request.get_cookie("prive", None) == prive_password

        if is_private_session:
            extra_left = """<a href="?prive="><div class="left_item"><div class="left_item_inner">Retour mode normal</div></div></a>"""

        # Liste privee
        try:
            with open("exercices/prive.txt", "r") as fhdl:
                prive = fhdl.read().replace("/", os.sep).splitlines()
        except FileNotFoundError:
            prive = []

        if "sim" in request.query:
            this_template = simulator_template
            if request.query["sim"] == "debug":
                code = debug_code

            elif not request.query["sim"] == "nouveau":
                try:
                    request.query["sim"] = base64.b64decode(unquote(request.query["sim"]))

                    if request.query["sim"].decode("utf-8")  in prive and not is_private_session:
                        raise FileNotFoundError()

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
            elif page == "accueil":
                try:
                    enonce = readFileBrokenEncoding(os.path.join("exercices", "accueil.html"))
                except FileNotFoundError:
                    enonce = "<h1>Bienvenue!</h1>"

            sections = OrderedDict()
            sections_names = {}
            for f in sorted(files):
                if f in prive and not is_private_session:
                    continue

                # YAHOG -- When in WSGI, Python adds 0xdc00 to every extended (e.g. accentuated) character, leading to
                # errors in utf-8 re-interpretation.
                if locale.getdefaultlocale() == (None, None):
                    f = encodeWSGI(f)

                fs = f.split(os.sep)
                soup = BeautifulSoup(readFileBrokenEncoding(os.path.join("exercices", f)), "html.parser")
                title = soup.find("h1")
                if title:
                    title = title.text

                if page == "tp":
                    if title:
                        k1 = title
                    else:
                        k1 = fs[1].replace(".html", "").replace("_", " ").encode('utf-8', 'replace')
                    sections[k1] = quote(base64.b64encode(f.encode('utf-8', 'replace')), safe='')
                else:
                    k1r = fs[1].replace("_", " ").encode('utf-8', 'replace')
                    if k1r not in sections_names:
                        try:
                            k1 = readFileBrokenEncoding(os.path.join("exercices", page, fs[1], 'nom.txt'))
                        except FileNotFoundError:
                            k1 = fs[1].replace("_", " ").encode('utf-8', 'replace')
                        sections_names[k1r] = k1

                    if sections_names[k1r] not in sections:
                        sections[sections_names[k1r]] = OrderedDict()

                    if title:
                        k2 = title
                    else:
                        k2 = fs[2].replace(".html", "").replace("_", " ").encode('utf-8', 'replace')

                    sections[sections_names[k1r]][k2] = quote(base64.b64encode(f.encode('utf-8', 'replace')), safe='')

            if page != "accueil" and len(sections) == 0:
                sections = {"Aucune section n'est disponible en ce moment.": {}}

            if page == "exo":
                title = "Exercices formatifs"
            elif page == "tp":
                title = "Travaux pratiques"
            elif page == "demo":
                title = "Démonstrations"
        lang = request.get_cookie("lang")
        if lang not in ['fr', 'en']:
            lang = default_lang
        i18NPlugin.set_lang(lang)

        return template(this_template, code=code, lang=lang, enonce=enonce, solution=solution,
                        page=page, title=title, sections=sections, identifier=identifier,
                        rand=random.randint(0, 2**16), extra_left=extra_left)


    @app.route('/static/<filename:path>')
    def static_serve(filename):
        return static_file(filename, root='./interface/static/')


    @app.post('/download/')
    def download():
        simParameter = unquote(request.forms.get('sim'))
        try:
            filename = base64.b64decode(simParameter).decode("utf-8")
            filename = os.path.splitext(os.path.basename(filename))[0]
        except binascii.Error:
            filename = 'source'
        data = request.forms.get('data')
        data = encodeWSGI(data)
        response.headers['Content-Type'] = 'text/plain; charset=UTF-8'
        response.headers['Content-Disposition'] = 'attachment; filename="%s.txt"' % filename
        return data
    return I18NMiddleware(app, i18NPlugin)


def http_server():
    bottle.run(app=get(), host='0.0.0.0', port=8000, server="gevent", debug=True)


def display_amount_users(signum, stack):
    print("Number of clients:", len(connected))
    print(connected)
    print("Number of interpreters:", len(interpreters))
    print(interpreters)
    sys.stdout.flush()

def translate_retval(lang, values):
    for i in range(len(values)):
        # Verification if message support i18n
        if values[i][0] == 'codeerror':
            if type(values[i][2]) == i18n.I18n:
                values[i] = (values[i][0], values[i][1], values[i][2].getText(lang))
        elif values[i][0] == 'disassembly':
            if type(values[i][1]) == i18n.I18n:
                values[i][1] = values[i][1].getText(lang)
    return values


if hasattr(signal, 'SIGUSR1'):
    signal.signal(signal.SIGUSR1, display_amount_users)


if __name__ == '__main__':
    if DEBUG:
        p = Process(target=http_server)
        p.start()

    # Websocket Server
    start_server = websockets.serve(handler, '0.0.0.0', 31415)
    if "uvloop" in globals():
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("Using uvloop")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

    if DEBUG:
        p.join()
