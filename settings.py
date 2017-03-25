import time

_settings = {"PCbehavior": "+8",            # Can be "+0", "+8"
             "PCspecialbehavior": False,    # True or False, whether we want to turn on or off the +4 for PC
                                            # with special instructions (STR/STM/PUSH from PC and dataop with
                                            # PC shifted by register)
             "allowuserswitchmode": True,   # True or False, indicates if the user can change the LSB bits of the CPSR
                                            # (that is, changing the mode of the processor). Technically forbidden
                                            # if we strictly follow ARMv4 specs, but it might be handy in some cases.
             "runmaxit": 2500,              # Maximum number of non-stop iterations
             "maxhistorylength": 1000,      # Maximum history depth
             "fillValue": 0xFF,             # Value used to fill non-initialized (but declared) memory
             "maxtotalmem": 0x10000,        # Maximum amount of memory per simulator
             }

def getSetting(name):
    return _settings[name]

def setSettings(settings):
    pass
