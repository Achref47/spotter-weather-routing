"""Domain errors that the API layer turns into clear user messages."""


class TripError(Exception):
    """Base class for expected, user-facing failures."""


class GeocodingError(TripError):
    """A place could not be located, or the geocoding service failed."""