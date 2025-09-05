import time
from postgres.incoming import Incoming
from postgres.outgoing import Outgoing

outgoing = Outgoing()
incoming = Incoming(outgoing)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting…")
