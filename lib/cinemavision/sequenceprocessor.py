import random
import time
import datetime
import database as DB
import sequence
import scrapers
import ratings
import actions
import util


# Playabe is implemented as a dict to be easily serializable to JSON
class Playable(dict):
    type = None

    @property
    def path(self):
        return self['path']

    def __repr__(self):
        return '{0}: {1}'.format(self.type, repr(self.path))


class Image(Playable):
    type = 'IMAGE'

    def __init__(self, path, duration=10, set_number=0, set_id=None, fade=0, *args, **kwargs):
        Playable.__init__(self, *args, **kwargs)
        self['path'] = path
        self['duration'] = duration
        self['setNumber'] = set_number
        self['setID'] = set_id
        self['fade'] = fade

    def __repr__(self):
        return 'IMAGE ({0}s): {1}'.format(self.duration, self.path)

    @property
    def setID(self):
        return self['setID']

    @property
    def duration(self):
        return self['duration']

    @duration.setter
    def duration(self, val):
        self['duration'] = val

    @property
    def setNumber(self):
        return self['setNumber']

    @property
    def fade(self):
        return self['fade']


class Song(Playable):
    type = 'SONG'

    def __init__(self, path, duration=0, *args, **kwargs):
        self['path'] = path
        self['duration'] = duration
        Playable.__init__(self, *args, **kwargs)

    @property
    def duration(self):
        return self['duration']

    @property
    def durationInt(self):
        return int(self['duration'])


class ImageQueue(dict):
    type = 'IMAGE.QUEUE'

    def __init__(self, handler, s_item, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._handler = handler
        self.sItem = s_item
        self.maxDuration = s_item.getLive('duration') * 60
        self.pos = -1
        self.transition = None
        self.transitionDuration = 400
        self.music = None
        self.musicVolume = 85
        self.musicFadeIn = 3.0
        self.musicFadeOut = 3.0

    def __iadd__(self, other):
        for o in other:
            self.duration += o.duration

        self.queue += other
        return self

    def __contains__(self, images):
        paths = [i.path for i in self.queue]
        if isinstance(images, list):
            for i in images:
                if i.path in paths:
                    return True
        else:
            return images.path in paths

        return False

    def __repr__(self):
        return '{0}: {1}secs'.format(self.type, self.duration)

    def reset(self):
        self.pos = -1

    def size(self):
        return len(self.queue)

    @property
    def duration(self):
        return self.get('duration', 0)

    @duration.setter
    def duration(self, val):
        self['duration'] = val

    @property
    def queue(self):
        return self.get('queue', [])

    @queue.setter
    def queue(self, q):
        self['queue'] = q

    def current(self):
        return self.queue[self.pos]

    def add(self, image):
        self.queue.append(image)

    def next(self, start=0, extend=False):
        overtime = start and time.time() - start >= self.maxDuration
        if overtime and not self.current().setNumber:
            return None

        if self.pos >= self.size() - 1:
            if extend or not overtime:
                return self._next()
            else:
                return None

        self.pos += 1

        return self.queue[self.pos]

    def _next(self):
        util.DEBUG_LOG('ImageQueue: Requesting next...')
        images = self._handler.next(self)
        if not images:
            util.DEBUG_LOG('ImageQueue: No next images')
            return None

        util.DEBUG_LOG('ImageQueue: {0} returned'.format(len(images)))
        self.queue += images
        self.pos += 1

        return self.current()

    def prev(self):
        if self.pos < 1:
            return None
        self.pos -= 1

        return self.current()

    def mark(self, image):
        if not image.setNumber:
            util.DEBUG_LOG('ImageQueue: Marking image as watched')
            self._handler.mark(image)

    def onFirst(self):
        return self.pos == 0

    def onLast(self):
        return self.pos == self.size() - 1


class Video(Playable):
    type = 'VIDEO'

    def __init__(self, path, user_agent='', duration=0, set_id=None):
        self['path'] = path
        self['userAgent'] = user_agent
        self['duration'] = duration
        self['setID'] = set_id

    @property
    def setID(self):
        return self['setID']

    @property
    def userAgent(self):
        return self['userAgent']

    @property
    def duration(self):
        return self.get('duration', 0)


class VideoQueue(dict):
    type = 'VIDEO.QUEUE'

    def __init__(self, handler, s_item, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self._handler = handler
        self.sItem = s_item
        self.duration = 0
        self['queue'] = []

    def __contains__(self, video):
        paths = [v.path for v in self.queue]
        return video.path in paths

    def __repr__(self):
        return '{0}: {1}secs'.format(self.type, self.duration)

    def append(self, video):
        self.duration += video.duration

        self['queue'].append(video)

    @property
    def queue(self):
        return self['queue']

    @queue.setter
    def queue(self, q):
        self['queue'] = q

    def mark(self, video):
        util.DEBUG_LOG('VideoQueue: Marking video as watched')
        self._handler.mark(video)


class Feature(Video):
    type = 'FEATURE'

    def __repr__(self):
        return 'FEATURE [ {0} ]:\n    Path: {1}\n    Rating: ({2})\n    Genres: {3}\n    3D: {4}\n    Audio: {5}'.format(
            repr(self.title),
            repr(self.path),
            self.rating,
            ', '.join(self.genres),
            self.is3D and 'Yes' or 'No',
            self.audioFormat
        )

    @property
    def ID(self):
        return self.get('ID', '')

    @ID.setter
    def ID(self, val):
        self['ID'] = val

    @property
    def dbType(self):
        return self.get('dbType', '')

    @dbType.setter
    def dbType(self, val):
        self['dbType'] = val

    @property
    def title(self):
        return self.get('title', '')

    @title.setter
    def title(self, val):
        self['title'] = val

    @property
    def rating(self):
        if not getattr(self, '_rating', None):
            ratingString = self.get('rating')
            if ratingString:
                self._rating = ratings.getRating(ratingString)
            else:
                self._rating = None
        return self._rating

    @rating.setter
    def rating(self, val):
        self['rating'] = val

    @property
    def genres(self):
        return self.get('genres', [])

    @genres.setter
    def genres(self, val):
        self['genres'] = val

    @property
    def is3D(self):
        return self.get('is3D', False)

    @is3D.setter
    def is3D(self, val):
        self['is3D'] = val

    @property
    def audioFormat(self):
        return self.get('audioFormat', '')

    @audioFormat.setter
    def audioFormat(self, val):
        self['audioFormat'] = val

    @property
    def thumb(self):
        return self.get('thumbnail', '')

    @thumb.setter
    def thumb(self, val):
        self['thumbnail'] = val

    @property
    def runtime(self):
        return self.get('runtime', '')

    @runtime.setter
    def runtime(self, val):
        self['runtime'] = val

    @property
    def year(self):
        return self.get('year', '')

    @year.setter
    def year(self, val):
        self['year'] = val

    @property
    def durationMinutesDisplay(self):
        if not self.runtime:
            return

        return '{0} minutes'.format(self.runtime/60)


class Action(dict):
    type = 'ACTION'

    def __init__(self, processor, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.processor = processor
        self['path'] = processor.path

    def __repr__(self):
        return '{0}: {1} - {2}'.format(self.type, self['path'], self.processor)

    def run(self):
        self.processor.run()


class FeatureHandler:
    @DB.session
    def getRatingBumper(self, sItem, feature, image=False):
        try:
            if sItem.getLive('ratingStyleSelection') == 'style':
                return DB.RatingsBumpers.select().where(
                    (DB.RatingsBumpers.system == feature.rating.system) &
                    (DB.RatingsBumpers.name == feature.rating.name) &
                    (DB.RatingsBumpers.is3D == feature.is3D) &
                    (DB.RatingsBumpers.isImage == image) &
                    (DB.RatingsBumpers.style == sItem.getLive('ratingStyle'))
                )[0]

            else:
                return random.choice(
                    [
                        x for x in DB.RatingsBumpers.select().where(
                            (DB.RatingsBumpers.system == feature.rating.system) &
                            (DB.RatingsBumpers.name == feature.rating.name) &
                            (DB.RatingsBumpers.is3D == feature.is3D) &
                            (DB.RatingsBumpers.isImage == image)
                        )
                    ]
                )
        except IndexError:
            return None

    def __call__(self, caller, sItem):
        count = sItem.getLive('count')

        util.DEBUG_LOG('[{0}] x {1}'.format(sItem.typeChar, count))

        features = caller.featureQueue[:count]
        caller.featureQueue = caller.featureQueue[count:]
        playables = []
        mediaType = sItem.getLive('ratingBumper')

        for f in features:
            bumper = None
            if mediaType == 'video':
                bumper = self.getRatingBumper(sItem, f)
                if bumper:
                    playables.append(Video(bumper.path))
                    util.DEBUG_LOG('    - Video Rating: {0}'.format(repr(bumper.path)))
            if mediaType == 'image' or mediaType == 'video' and not bumper:
                bumper = self.getRatingBumper(sItem, f, image=True)
                if bumper:
                    playables.append(Image(bumper.path, duration=10, fade=3000))
                    util.DEBUG_LOG('    - Image Rating: {0}'.format(repr(bumper.path)))

            playables.append(f)

        return playables


class TriviaHandler:
    def __init__(self):
        pass

    def __call__(self, caller, sItem):
        duration = sItem.getLive('duration')

        util.DEBUG_LOG('[{0}] {1}m'.format(sItem.typeChar, duration))

        durationLimit = duration * 60
        queue = ImageQueue(self, sItem)
        queue.transition = sItem.getLive('transition')
        queue.transitionDuration = sItem.getLive('transitionDuration')

        vqueue = VideoQueue(self, sItem)

        for slides in self.getTriviaImages(sItem):
            if isinstance(slides, Video):
                vqueue.append(slides)
            else:
                queue += slides

            if queue.duration + vqueue.duration >= durationLimit:
                break

        ret = []

        if queue.duration:
            ret.append(queue)
            queue.maxDuration -= vqueue.duration
        if vqueue.duration:
            ret.append(vqueue)

        self.addMusic(sItem, queue)

        return ret

    @DB.session
    def addMusic(self, sItem, queue):
        mode = sItem.getLive('music')
        if mode == 'off':
            return

        if mode == 'content':
            queue.music = [Song(s.path, s.duration) for s in DB.Song.select().order_by(DB.fn.Random())]
        elif mode == 'dir':
            path = sItem.getLive('musicDir')
            if not path:
                return

            import mutagen
            mutagen.setFileOpener(util.vfs.File)

            queue.music = []
            for p in util.listFilePaths(path):
                try:
                    data = mutagen.File(p)
                except:
                    data = None
                    util.ERROR()

                d = 0
                if data:
                    d = data.info.length
                queue.music.append(Song(p, d))

            random.shuffle(queue.music)
        elif mode == 'file':
            path = sItem.getLive('musicFile')
            if not path:
                return

            import mutagen
            mutagen.setFileOpener(util.vfs.File)

            data = mutagen.File(path)
            d = 0
            if data:
                d = data.info.length
            queue.music = [Song(path, d)]

        duration = sum([s.duration for s in queue.music])

        if duration:  # Maybe they were all zero - we'll be here forever :)
            while duration < queue.duration:
                for i in range(len(queue.music)):
                    song = queue.music[i]
                    duration += song.duration
                    queue.music.append(song)
                    if duration >= queue.duration:
                        break

        queue.musicVolume = util.getSettingDefault('trivia.musicVolume')
        queue.musicFadeIn = util.getSettingDefault('trivia.musicFadeIn')
        queue.musicFadeOut = util.getSettingDefault('trivia.musicFadeOut')

    @DB.session
    def getTriviaImages(self, sItem):  # TODO: Probably re-do this separate for slides and video?
        useVideo = sItem.getLive('format') == 'video'
        # Do this each set in reverse so the setNumber counts down
        clue = sItem.getLive('cDuration')
        durations = (
            sItem.getLive('aDuration'),
            clue, clue, clue, clue, clue, clue, clue, clue, clue, clue,
            sItem.getLive('qDuration')
        )
        for trivia in DB.Trivia.select().order_by(DB.fn.Random()):
            if useVideo:
                if trivia.type != 'video':
                    continue
            else:
                if trivia.type == 'video':
                    continue

            try:
                DB.WatchedTrivia.get((DB.WatchedTrivia.WID == trivia.TID) & DB.WatchedTrivia.watched)
            except DB.peewee.DoesNotExist:
                yield self.createTriviaImages(sItem, trivia, durations)

        # Grab the oldest 4 trivias, shuffle and yield... repeat
        pool = []
        for watched in DB.WatchedTrivia.select().where(DB.WatchedTrivia.watched).order_by(DB.WatchedTrivia.date):
            try:
                trivia = DB.Trivia.get(DB.Trivia.TID == watched.WID)
            except DB.peewee.DoesNotExist:
                continue

            if useVideo:
                if trivia.type != 'video':
                    continue
            else:
                if trivia.type == 'video':
                    continue

            pool.append(trivia)

            if len(pool) > 3:
                random.shuffle(pool)
                for t in pool:
                    yield self.createTriviaImages(sItem, t, durations)
                pool = []

        if pool:
            random.shuffle(pool)
            for t in pool:
                yield self.createTriviaImages(sItem, t, durations)

    def createTriviaImages(self, sItem, trivia, durations):
        if trivia.type == 'video':
            return Video(trivia.answerPath, duration=trivia.duration, set_id=trivia.TID)
        else:
            clues = [getattr(trivia, 'cluePath{0}'.format(x)) for x in range(9, -1, -1)]
            paths = [trivia.answerPath] + clues + [trivia.questionPath]
            slides = []
            setNumber = 0
            for p, d in zip(paths, durations):
                if p:
                    slides.append(Image(p, d, setNumber, trivia.TID))
                    setNumber += 1

            slides.reverse()  # Slides are backwards

            if len(slides) == 1:  # This is a still - set duration accordingly
                slides[0].duration = sItem.getLive('sDuration')

            return slides

    def next(self, image_queue):
        for slides in self.getTriviaImages(image_queue.sItem):
            if slides not in image_queue:
                return slides
        return None

    @DB.session
    def mark(self, image):
        trivia = DB.WatchedTrivia.get_or_create(WID=image.setID)[0]
        trivia.update(
            watched=True,
            date=datetime.datetime.now()
        ).where(DB.WatchedTrivia.WID == image.setID).execute()


class TrailerHandler:
    def __init__(self):
        self.caller = None

    def __call__(self, caller, sItem):
        self.caller = caller

        source = sItem.getLive('source')

        playables = []
        if source == 'itunes':
            playables = self.scraperHandler(sItem, 'iTunes')
        elif source == 'kodidb':
            playables = self.scraperHandler(sItem, 'kodiDB')
        elif source == 'dir' or source == 'content':
            playables = self.dirHandler(sItem)
        elif source == 'file':
            playables = self.fileHandler(sItem)

        if not playables:
            util.DEBUG_LOG('[{0}] {1}: NOT SHOWING'.format(sItem.typeChar, source))

        return playables

    def filter(self, sItem, trailers):
        filtered = trailers

        ratingLimitMethod = sItem.getLive('ratingLimit')

        if ratingLimitMethod and ratingLimitMethod != 'none':
            if ratingLimitMethod == 'max':
                maxr = ratings.getRating(sItem.getLive('ratingMax').replace('.', ':', 1))
                util.DEBUG_LOG('    - Limiting to ratings less than: {0}'.format(str(maxr)))
                filtered = [f for f in filtered if f.rating.value <= maxr.value]
            elif self.caller.ratings:
                minr = min(self.caller.ratings.values(), key=lambda x: x.value)
                maxr = max(self.caller.ratings.values(), key=lambda x: x.value)
                util.DEBUG_LOG('    - Matching ratings between {0} and {1}'.format(str(minr), str(maxr)))
                filtered = [f for f in filtered if minr.value <= f.rating.value <= maxr.value]

        if sItem.getLive('limitGenre'):
            if self.caller.genres:
                util.DEBUG_LOG('    - Filtering by genres')
                filtered = [f for f in filtered if any(x in self.caller.genres for x in f.genres)]

        return filtered

    @DB.session
    def unwatched(self, trailers):
        ret = []
        for t in trailers:
            try:
                DB.WatchedTrailers.get((DB.WatchedTrailers.WID == t.ID) & DB.WatchedTrailers.watched)
            except DB.peewee.DoesNotExist:
                ret.append(t)

        return ret

    def convertItunesURL(self, url, res):
        repl = None
        for r in ('h480p', 'h720p', 'h1080p'):
            if r in url:
                repl = r
                break
        if not repl:
            return url

        return url.replace(repl, 'h{0}'.format(res))

    @DB.session
    def oldest(self, sItem, source):
        util.DEBUG_LOG('    - All scraper trailers watched - using oldest trailers')

        ratingLimitMethod = sItem.getLive('ratingLimit')

        if ratingLimitMethod and ratingLimitMethod != 'none':
            if ratingLimitMethod == 'max':
                minr = ratings.MPAA.G
                maxr = ratings.getRating(sItem.getLive('ratingMax').replace('.', ':', 1))
            elif self.caller.ratings:
                minr = min(self.caller.ratings.values(), key=lambda x: x.value)
                maxr = max(self.caller.ratings.values(), key=lambda x: x.value)

            trailers = [
                t for t in DB.WatchedTrailers.select().where(
                    DB.WatchedTrailers.url != 'BROKEN'
                ).order_by(
                    DB.WatchedTrailers.date
                ) if minr.value <= ratings.getRating(t.rating).value <= maxr.value
            ]
        else:
            trailers = [
                t for t in DB.WatchedTrailers.select().where(
                    DB.WatchedTrailers.source == source & DB.WatchedTrailers.url != 'BROKEN'
                ).order_by(DB.WatchedTrailers.date)
            ]

        if not trailers:
            return []
        # Take the oldest for count + a few to make the random more random
        if sItem.getLive('limitGenre'):
            if self.caller.genres:
                trailers = [t for t in trailers if any(x in self.caller.genres for x in (t.genres or '').split(','))]
        count = sItem.getLive('count')
        if len(trailers) > count:
            trailers = random.sample(trailers[:count + 5], count)

        now = datetime.datetime.now()

        for t in trailers:
            DB.WatchedTrailers.update(
                watched=True,
                date=now
            ).where(DB.WatchedTrailers.WID == t.WID).execute()

        return [Video(self.convertItunesURL(t.url, sItem.getLive('quality')), t.userAgent) for t in trailers]

    @DB.session
    def scraperHandler(self, sItem, source):
        count = sItem.getLive('count')

        util.DEBUG_LOG('[{0}] {1} x {2}'.format(sItem.typeChar, source, count))

        trailers = scrapers.getTrailers(source)
        trailers = self.filter(sItem, trailers)

        if util.getSettingDefault('trailer.playUnwatched'):
            util.DEBUG_LOG('    - Filtering out watched')
            trailers = self.unwatched(trailers)

        if not trailers:
            return self.oldest(sItem, source)

        if len(trailers) > count:
            trailers = random.sample(trailers, count)

        now = datetime.datetime.now()
        quality = sItem.getLive('quality')

        valid = []

        for t in trailers:
            url = t.getPlayableURL(quality)

            if url:
                valid.append((url, t))

            try:
                trailer = DB.WatchedTrailers.get(DB.WatchedTrailers.WID == t.ID)
                trailer.update(
                    source=source,
                    watched=True,
                    date=now,
                    title=t.title,
                    url=url or 'BROKEN',
                    userAgent=t.userAgent,
                    rating=str(t.rating),
                    genres=','.join(t.genres)
                ).execute()
            except DB.peewee.DoesNotExist:
                DB.WatchedTrailers.create(
                    WID=t.ID,
                    source=source,
                    watched=True,
                    date=now,
                    title=t.title,
                    url=url or 'BROKEN',
                    userAgent=t.userAgent,
                    rating=str(t.rating),
                    genres=','.join(t.genres)
                )

        if not valid:
            return self.oldest(sItem, source)

        return [Video(url, trailer.userAgent) for url, trailer in valid]

    def dirHandler(self, sItem):
        count = sItem.getLive('count')

        if sItem.getLive('source') == 'content':
            path = util.pathJoin(self.caller.contentPath, 'Trailers')
            util.DEBUG_LOG('[{0}] Content x {1}'.format(sItem.typeChar, count))
        else:
            path = sItem.getLive('dir')
            util.DEBUG_LOG('[{0}] Directory x {1}'.format(sItem.typeChar, count))

        if not path:
            util.DEBUG_LOG('    - Empty path!')
            return []

        try:
            files = util.vfs.listdir(path)
            files = random.sample(files, count)
            return [Video(util.pathJoin(path, p)) for p in files]
        except:
            util.ERROR()
            return []

    def fileHandler(self, sItem):
        path = sItem.getLive('file')
        if not path:
            return []

        util.DEBUG_LOG('[{0}] File: {1}'.format(sItem.typeChar, repr(path)))

        return [Video(path)]


class VideoBumperHandler:
    def __init__(self):
        self.caller = None
        self.handlers = {
            '3D.intro': self._3DIntro,
            '3D.outro': self._3DOutro,
            'countdown': self.countdown,
            'courtesy': self.courtesy,
            'feature.intro': self.featureIntro,
            'feature.outro': self.featureOutro,
            'intermission': self.intermission,
            'short.film': self.shortFilm,
            'theater.intro': self.theaterIntro,
            'theater.outro': self.theaterOutro,
            'trailers.intro': self.trailersIntro,
            'trailers.outro': self.trailersOutro,
            'trivia.intro': self.triviaIntro,
            'trivia.outro': self.triviaOutro,
            'dir': self.dir,
            'file': self.file
        }

    def __call__(self, caller, sItem):
        self.caller = caller
        util.DEBUG_LOG('[{0}] {1}'.format(sItem.typeChar, sItem.display()))
        playables = self.handlers[sItem.vtype](sItem)
        if playables:
            if sItem.vtype == 'dir':
                util.DEBUG_LOG('    - {0}'.format(' x {0}'.format(sItem.count) or ''))
        else:
            util.DEBUG_LOG('    - {0}'.format('NOT SHOWING'))

        return playables

    @DB.session
    def defaultHandler(self, sItem):
        is3D = self.caller.currentFeature.is3D and sItem.play3D

        if sItem.random:
            util.DEBUG_LOG('    - Random')
            try:
                bumper = random.choice([x for x in DB.VideoBumpers.select().where((DB.VideoBumpers.type == sItem.vtype) & (DB.VideoBumpers.is3D == is3D))])
                return [Video(bumper.path)]
            except IndexError:
                util.DEBUG_LOG('    - No matches!')
                pass

            if is3D and util.getSettingDefault('bumper.fallback2D'):
                util.DEBUG_LOG('    - Falling back to 2D bumper')
                try:
                    bumper = random.choice([x for x in DB.VideoBumpers.select().where((DB.VideoBumpers.type == sItem.vtype))])
                    return [Video(bumper.path)]
                except IndexError:
                    util.DEBUG_LOG('    - No matches!')
                    pass
        else:
            util.DEBUG_LOG('    - Via source')
            if sItem.source:
                return [Video(sItem.source)]
            else:
                util.DEBUG_LOG('    - Empty path!')

        return []

    def _3DIntro(self, sItem):
        if not self.caller.currentFeature.is3D:
            return []
        return self.defaultHandler(sItem)

    def _3DOutro(self, sItem):
        if not self.caller.currentFeature.is3D:
            return []
        return self.defaultHandler(sItem)

    def countdown(self, sItem):
        return self.defaultHandler(sItem)

    def courtesy(self, sItem):
        return self.defaultHandler(sItem)

    def featureIntro(self, sItem):
        return self.defaultHandler(sItem)

    def featureOutro(self, sItem):
        return self.defaultHandler(sItem)

    def intermission(self, sItem):
        return self.defaultHandler(sItem)

    def shortFilm(self, sItem):
        return self.defaultHandler(sItem)

    def theaterIntro(self, sItem):
        return self.defaultHandler(sItem)

    def theaterOutro(self, sItem):
        return self.defaultHandler(sItem)

    def trailersIntro(self, sItem):
        return self.defaultHandler(sItem)

    def trailersOutro(self, sItem):
        return self.defaultHandler(sItem)

    def triviaIntro(self, sItem):
        return self.defaultHandler(sItem)

    def triviaOutro(self, sItem):
        return self.defaultHandler(sItem)

    def file(self, sItem):
        if sItem.file:
            return [Video(sItem.file)]
        else:
            return []

    def dir(self, sItem):
        if not sItem.dir:
            return []

        try:
            files = util.vfs.listdir(sItem.dir)
            if sItem.random:
                files = random.sample(files, sItem.count)
            else:
                files = files[:sItem.count]

            return [Video(util.pathJoin(sItem.dir, p)) for p in files]
        except:
            util.ERROR()
            return []


class AudioFormatHandler:
    @DB.session
    def __call__(self, caller, sItem):
        bumper = None
        method = sItem.getLive('method')
        fallback = sItem.getLive('fallback')
        format_ = sItem.getLive('format')

        util.DEBUG_LOG('[{0}] Method: {1} Fallback: {2} Format: {3}'.format(sItem.typeChar, method, fallback, format_))

        is3D = caller.currentFeature.is3D and sItem.play3D

        if method == 'af.detect':
            util.DEBUG_LOG('    - Detect')
            if caller.currentFeature.audioFormat:
                try:
                    bumper = random.choice(
                        [x for x in DB.AudioFormatBumpers.select().where(
                            (DB.AudioFormatBumpers.format == caller.currentFeature.audioFormat) & (DB.AudioFormatBumpers.is3D == is3D)
                        )]
                    )
                    util.DEBUG_LOG('    - Detect: Using bumper based on feature codec info ({0})'.format(caller.currentFeature.title))
                except IndexError:
                    util.DEBUG_LOG('    - Detect: No codec matches!')
                    if is3D and util.getSettingDefault('bumper.fallback2D'):
                        try:
                            bumper = random.choice(
                                [x for x in DB.AudioFormatBumpers.select().where(DB.AudioFormatBumpers.format == caller.currentFeature.audioFormat)]
                            )
                            util.DEBUG_LOG('    - Using bumper based on feature codec info and falling back to 2D ({0})'.format(caller.currentFeature.title))
                        except IndexError:
                            pass
            else:
                util.DEBUG_LOG('    - No feature audio format!')

        if (
            format_ and not bumper and (
                method == 'af.format' or (
                    method == 'af.detect' and fallback == 'af.format'
                )
            )
        ):
            util.DEBUG_LOG('    - Format')
            try:
                bumper = random.choice(
                    [x for x in DB.AudioFormatBumpers.select().where(
                        (DB.AudioFormatBumpers.format == format_) & (DB.AudioFormatBumpers.is3D == is3D)
                    )]
                )
                util.DEBUG_LOG('    - Format: Using bumper based on setting ({0})'.format(repr(caller.currentFeature.title)))
            except IndexError:
                util.DEBUG_LOG('    - Format: No matches!')
                if is3D and util.getSettingDefault('bumper.fallback2D'):
                    try:
                        bumper = random.choice([x for x in DB.AudioFormatBumpers.select().where(DB.AudioFormatBumpers.format == format_)])
                        util.DEBUG_LOG('    - Using bumper based on format setting and falling back to 2D ({0})'.format(caller.currentFeature.title))
                    except IndexError:
                        pass
        if (
            sItem.getLive('file') and not bumper and (
                method == 'af.file' or (
                    method == 'af.detect' and fallback == 'af.file'
                )
            )
        ):
            util.DEBUG_LOG('    - File: Using bumper based on setting ({0})'.format(caller.currentFeature.title))
            return [Video(sItem.getLive('file'))]

        if bumper:
            return [Video(bumper.path)]

        util.DEBUG_LOG('    - NOT SHOWING')
        return []


class ActionHandler:
    def __call__(self, caller, sItem):
        if not sItem.file:
            util.DEBUG_LOG('[{0}] NO PATH SET'.format(sItem.typeChar))
            return []

        util.DEBUG_LOG('[{0}] {1}'.format(sItem.typeChar, sItem.file))
        processor = actions.ActionFileProcessor(sItem.file)
        return [Action(processor)]


class SequenceProcessor:
    def __init__(self, sequence_path, db_path=None, content_path=None):
        DB.initialize(db_path)
        self.pos = -1
        self.size = 0
        self.sequence = []
        self.featureQueue = []
        self.playables = []
        self.ratings = {}
        self.genres = []
        self.contentPath = content_path
        self.loadSequence(sequence_path)
        self.createDefaultFeature()

    def atEnd(self):
        return self.pos >= self.end

    @property
    def currentFeature(self):
        return self.featureQueue and self.featureQueue[0] or self.defaultFeature

    def createDefaultFeature(self):
        self.defaultFeature = Feature('')
        self.defaultFeature.title = 'Default Feature'
        self.defaultFeature.rating = 'MPAA:NR'
        self.defaultFeature.audioFormat = 'Other'

    def addFeature(self, feature):
        if feature.rating:
            self.ratings[str(feature.rating)] = feature.rating

        if feature.genres:
            self.genres += feature.genres

        self.featureQueue.append(feature)

    def commandHandler(self, sItem):
        if sItem.condition == 'feature.queue=full' and not self.featureQueue:
            return 0
        if sItem.condition == 'feature.queue=empty' and self.featureQueue:
            return 0
        if sItem.command == 'back':
            return sItem.arg * -1
        elif sItem.command == 'skip':
            return sItem.arg

    # SEQUENCE PROCESSING
    handlers = {
        'feature': FeatureHandler(),
        'trivia': TriviaHandler(),
        'trailer': TrailerHandler(),
        'video': VideoBumperHandler(),
        'audioformat': AudioFormatHandler(),
        'action': ActionHandler(),
        'command': commandHandler
    }

    def process(self):
        util.DEBUG_LOG('Processing sequence...')
        util.DEBUG_LOG('Feature count: {0}'.format(len(self.featureQueue)))
        util.DEBUG_LOG('Ratings: {0}'.format(', '.join(self.ratings.keys())))
        util.DEBUG_LOG('Genres: {0}'.format(', '.join(self.genres)))

        if self.featureQueue:
            util.DEBUG_LOG('\n\n' + '\n\n'.join([str(f) for f in self.featureQueue]) + '\n.')
        else:
            util.DEBUG_LOG('NO FEATURES QUEUED')

        self.playables = []
        pos = 0
        while pos < len(self.sequence):
            sItem = self.sequence[pos]

            if not sItem.enabled:
                util.DEBUG_LOG('[{0}] ({1}) DISABLED'.format(sItem.typeChar, sItem.display()))
                pos += 1
                continue

            handler = self.handlers.get(sItem._type)
            if handler:
                if sItem._type == 'command':
                    offset = handler(self, sItem)
                    pos += offset
                    if offset:
                        continue
                else:
                    self.playables += handler(self, sItem)

            pos += 1
        self.playables.append(None)  # Keeps it from being empty until AFTER the last item
        self.end = len(self.playables) - 1

        util.DEBUG_LOG('Sequence processing finished')

    def loadSequence(self, sequence_path):
        self.sequence = sequence.loadSequence(sequence_path)
        util.DEBUG_LOG('')
        for si in self.sequence:
            util.DEBUG_LOG('[- {0} -]'.format(si._type))
            for e in si._elements:
                util.DEBUG_LOG('{0}: {1}'.format(e['attr'], si.getLive(e['attr'])))

            util.DEBUG_LOG('')

    def next(self):
        if self.atEnd():
            return None

        self.pos += 1
        playable = self.playables[self.pos]

        return playable

    def prev(self):
        if self.pos > 0:
            self.pos -= 1

        playable = self.playables[self.pos]

        return playable
