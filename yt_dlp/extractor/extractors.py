import itertools
import os

from ..globals import LAZY_EXTRACTORS
from ..globals import extractors as _extractors_context

_CLASS_LOOKUP = None
if os.environ.get('YTDLP_NO_LAZY_EXTRACTORS'):
    LAZY_EXTRACTORS.value = False
else:
    try:
        from .lazy_extractors import _CLASS_LOOKUP
        LAZY_EXTRACTORS.value = True
    except ImportError:
        LAZY_EXTRACTORS.value = None

if not _CLASS_LOOKUP:
    from . import _extractors

    members = tuple(
        (name, getattr(_extractors, name))
        for name in dir(_extractors)
        if name.endswith('IE')
    )
    _CLASS_LOOKUP = dict(itertools.chain(
        # Add Youtube first to improve matching performance
        ((name, value) for name, value in members if '.youtube' in value.__module__),
        # Add Generic last so that it is the fallback
        ((name, value) for name, value in members if name != 'GenericIE'),
        (('GenericIE', _extractors.GenericIE),),
    ))

# We want to append to the main lookup
_current = _extractors_context.value
for name, ie in _CLASS_LOOKUP.items():
    _current.setdefault(name, ie)


def __getattr__(name):
    value = _CLASS_LOOKUP.get(name)
    if not value:
        raise AttributeError(f'module {__name__} has no attribute {name}')
    return value


# Replit custom extractor lazy-lookup registration
from . import _extractors as _replit_extractors
_generic = _current.pop('GenericIE', None)
for _name in ('StreamtapeIE', 'VidaraIE', 'VoeIE', 'HGCloudIE', 'LuluvdoIE', 'FilemoonByseIE', 'VidHideIE', 'PlaymogoIE', 'MixDropIE', 'SaucePlayerIE', 'FapticaIE', 'FappTimeIE', 'BornToBeFuckIE', 'FapNutIE', 'HornyLeakIE', 'HornySimpIE', 'HotLeakIE', 'LeakPornerIE', 'OnlyChicksHubIE', 'OnlyJerkIE', 'OnlyPornIE', 'PureLeaksIE', 'RealPornClipIE', 'SauceSenpaiIE', 'TheSaucelsIE', 'ThotChicksIE', 'ThotFlixIE', 'ThotsterIE', 'TittyTubeIE', 'XXVideosIE', 'ShareNudeIE', 'NSFW247IE', 'GoonityIE', 'PornlIE', 'SexvidIE', 'HotntubesIE', 'ThotPornIE', 'LewdStarsIE', 'SxyPrnIE', 'UncutXIE', 'GofileIE', 'EinthusanIE',):
    _custom = getattr(_replit_extractors, _name)
    _CLASS_LOOKUP.setdefault(_name, _custom)
    _current.setdefault(_name, _custom)
if _generic is not None:
    _current['GenericIE'] = _generic
del _custom, _generic, _name, _replit_extractors
