import polib

languages = [
    'en',
    'fr',
]

files = [
    'interface',
    'interpreter',
]

for lang in languages:
    path = './locale/{}/LC_MESSAGES'.format(lang)
    for file in files:
        po = polib.pofile(path + '/{}.po'.format(file))
        po.save_as_mofile(path + '/{}.mo'.format(file))

