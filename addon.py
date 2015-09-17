import sys

if __name__ == '__main__':
    arg = None
    if len(sys.argv) > 1:
        arg = sys.argv[1] or False

    if arg == 'trailer.clearWatched':
        from lib import settings
        settings.clearDBWatchedStatus()
    elif arg == 'experience':
        from lib import player
        player.begin()
    elif str(arg).startswith('movieid='):
        from lib import player
        player.begin(movieid=arg[8:])
    elif str(arg).startswith('episodeid='):
        from lib import player
        player.begin(episodeid=arg[10:])
    elif arg == 'selection':
        from lib import player
        player.begin(selection=True)
    elif arg == 'update.database':
        from lib import cvutil
        from lib import kodiutil
        cvutil.loadContent(from_settings=True)
        kodiutil.ADDON.openSettings()
    elif arg == 'feature.setRatingBumperStyle':
        from lib import cvutil
        cvutil.setRatingBumperStyle()
    elif arg == 'pastebin.paste.log':
        from lib import settings
        settings.pasteLog()
    else:
        from lib import main
        main.main()
