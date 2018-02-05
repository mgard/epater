import gettext, os, re, functools
from bottle import PluginError, request, template, DictMixin, TEMPLATE_PATH


def i18n_defaults(template, request):
    template.defaults['_'] = lambda msgid, options=None: request.app._(msgid) % options if options else request.app._(msgid)
    template.defaults['lang'] = lambda: request.app.lang


def i18n_template(*args, **kwargs):
    tpl = args[0] if args else None
    if tpl:
        tpl = os.path.join("{lang!s}/".format(lang=request.app.lang), tpl)
    eles = list(args)
    eles[0] = tpl
    args = tuple(eles)
    return template(*args, **kwargs)

def i18n_view(tmpl, **defaults):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            file = os.path.join("{lang!s}/".format(lang=request.app.lang), tmpl)
            result = func(*args, **kwargs)
            if isinstance(result, (dict, DictMixin)):
                tplvars = defaults.copy()
                tplvars.update(result)
                return template(file, **tplvars)
            elif result is None:
                return template(file, defaults)
            return result
        return wrapper
    return decorator


class I18NMiddleware(object):
    
    @property
    def header(self):
        return self._header
    @property
    def http_accept_language(self):
        return self.header.get('HTTP_ACCEPT_LANGUAGE')
    @property
    def app(self):
        return self._app
    
    def __init__(self, app, i18n, sub_app=True):
        self._app = app
        self.app.install(i18n)
        self._http_language = ""
        i18n.middleware = self
        
        if sub_app:
            for route in self.app.routes:
                if route.config.get('mountpoint'):
                    route.config.get('mountpoint').get('target').install(i18n)
    
    
    def __call__(self, e, h):
        self._http_language = e.get('HTTP_ACCEPT_LANGUAGE')
        self._header = e
        locale = e['PATH_INFO'].split('/')[1]
        for i18n in [plugin for plugin in self.app.plugins if plugin.name == 'i18n']:
            if locale in i18n.locales:
                self.app.lang = locale
                e['PATH_INFO'] = e['PATH_INFO'][len(locale)+1:]
        return self.app(e,h)


Middleware = I18NMiddleware

class I18NPlugin(object):
    name = 'i18n'
    api = 2
    
    @property
    def middleware(self):
        return self._middleware
    @middleware.setter
    def middleware(self, middleware):
        self._middleware = middleware
    @property
    def keyword(self):
        return self._keyword
    @property
    def locales(self):
        return self._locales
    @property
    def local_dir(self):
        return self._locale_dir
    
    def __init__(self, domain, locale_dir, lang_code=None, default='en', keyword='i18n'):
        self.domain = domain
        if locale_dir is None:
            raise PluginError('No locale directory found, please assign a right one.')
        self._locale_dir = locale_dir
        
        self._locales = self._get_languages(self._locale_dir)
        self._default = default
        self._lang_code = lang_code
        
        self._cache = {}
        self._apps = []
        self._keyword = keyword
    
    def _get_languages(self, directory):
        return [dir for dir in os.listdir(self._locale_dir) if os.path.isdir(os.path.join(directory, dir))]
    
    
    def setup(self, app):
        self._apps.append(app)
        for app in self._apps:
            app._ = lambda s: s
            
            if hasattr(app, 'add_hook'):
                # attribute hooks was renamed to _hooks in version 0.12.x and add_hook method was introduced instead.
                app.add_hook('before_request', self.prepare)
            else:
                app.hooks.add('before_request', self.prepare)
            
            app.__class__.lang = property(fget=lambda x: self.get_lang(), fset=lambda x, value: self.set_lang(value))
    
    def parse_accept_language(self, accept_language):
        if accept_language == None:
            return []
        languages = accept_language.split(",")
        locale_q_pairs = []
        
        for language in languages:
            if language.split(";")[0] == language:
                # no q => q = 1
                locale_q_pairs.append((language.strip(), "1"))
            else:
                locale = language.split(";")[0].strip()
                q = language.split(";")[1].split("=")[1]
                locale_q_pairs.append((locale, q))
        
        return locale_q_pairs
    
    
    def detect_locale(self):
        locale_q_pairs = self.parse_accept_language(self.middleware.http_accept_language)
        for pair in locale_q_pairs:
            for locale in self._locales:
                if pair[0].replace('-', '_').lower().startswith(locale.lower()):
                    return locale
        
        return self._default
    
    
    def get_lang(self):
        return self._lang_code
    
    def set_lang(self, lang_code=None):
        self._lang_code = lang_code
        if self._lang_code is None:
            self._lang_code = self.detect_locale()
        
        self.prepare()

    def prepare(self, *args, **kwargs):
        if self._lang_code is None:
            self._lang_code = self.detect_locale()
        
        if self._lang_code in list(self._cache.keys()):
            trans = self._cache[self._lang_code]
            if trans:
                trans.install()
                for app in self._apps:
                    app._ = trans.gettext
            else:
                for app in self._apps:
                    app._ = lambda s: s
            return
        try:
            trans = gettext.translation(self.domain, self._locale_dir, languages=[self._lang_code])
            trans.install()
            for app in self._apps:
                app._ = trans.gettext
            self._cache[self._lang_code] = trans
        except Exception as e:
            for app in self._apps:
                app._ = lambda s: s
            self._cache[self._lang_code] = None
    
    
    def apply(self, callback, route):
        return callback


Plugin = I18NPlugin
