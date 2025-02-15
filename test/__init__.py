import logging

# Prevents logging output in tests
log = logging.getLogger("nbxmpp")
log.setLevel(logging.CRITICAL)
