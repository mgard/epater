import gettext

class I18n:
    """
    This class is used for internationalization without a specific language.

    Objects can be stored as msgid from gettext or as str.
    """
    def __init__(self, msg, isSTR=False):
        if isSTR:
            self.content = [msg]
        else:
            self.content = [self.I18n_inner(msg)]

    def append(self, msg):
        if type(msg) == self.__class__:
            self.content += msg.content
        else:
            self.content.append(msg)

    def __iadd__(self, msg):
        self.append(msg)
        return self

    def format(self, *args, **kwargs):
        self.content[-1].format(*args, **kwargs)
        return self

    def getText(self, lang):
        """
        Return the localized translation

        :param lang: the language to translate
        """
        if type(lang) == str:
            lang = gettext.translation('interpreter', './locale', languages=[lang], fallback=True)
        result = ""
        for msg in self.content:
            if type(msg) == self.I18n_inner or type(msg) == self.__class__:
                result += msg.getText(lang)
            else:
                result += msg
        return result

    # Inner class
    class I18n_inner:
        def __init__(self, msg):
            self.msg = msg
            self.formatArg = None
            self.formatKwargs = None

        def format(self, *args, **kwargs):
            self.formatKwargs = kwargs
            self.formatArg = args
            return self

        def getText(self, t):
            if self.formatKwargs:
                for key, value in self.formatKwargs.items():
                    if type(value) == I18n or type(value) == self.__class__:
                        self.formatKwargs[key] = value.getText(t)
            if self.formatArg:
                resultArg = []
                for arg in self.formatArg:
                    if type(arg) == I18n or type(arg) == self.__class__:
                        resultArg.append(arg.getText(t))
                    else:
                        resultArg.append(arg)
                return t.gettext(self.msg).format(*resultArg, **self.formatKwargs)
            elif self.formatKwargs:
                return t.gettext(self.msg).format(**self.formatKwargs)
            else:
                return t.gettext(self.msg)

