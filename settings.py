import time

_settings = {"PCbehavior": "+8",        # Can be "+0", "+8", "real"
             "runmaxit": 1000}          # Maximum number of non-stop iterations

def getSetting(name):
    return _settings[name]

def setSettings(settings):
    pass