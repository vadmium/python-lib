from lib import event
from lib import cares
from socket import AF_UNSPEC
from itertools import compress

def resolve(event_driver, name, family=AF_UNSPEC):
    self = ResolveContext(event_driver)
    timer = event_driver.Timer()
    
    channel = cares.Channel(sock_state_cb=self.sock_state)
    
    channel.gethostbyname(name, family, self.host)
    while self.status is None:
        events = event.Any(self.files.values())
        
        timeout = channel.timeout()
        if timeout is not None:
            timer.start(timeout)
            events.add(timer)
        
        (trigger, args) = (yield events)
        timer.stop()
        
        if trigger is timer:
            ops = ()
        else:
            (fd, ops) = args
        channel.process_fd(*(fd if (op in ops) else None for op in self.ops))
    cares.check(self.status)
    raise StopIteration(self.hostent)

class ResolveContext:
    def __init__(self, event_driver):
        self.FileEvent = event_driver.FileEvent
        self.status = None
        self.files = dict()  # File events by file descriptor
        self.ops = (self.FileEvent.READ, self.FileEvent.WRITE)
    
    def sock_state(self, s, *ops):
        if any(ops):
            try:
                event = self.files[s]
            except LookupError:
                event = self.FileEvent(s)
                self.files[s] = event
            event.watch(compress(self.ops, ops))
        else:
            try:
                del self.files[s]
            except LookupError:
                pass
    
    def host(self, status, timeouts, hostent):
        self.status = status
        self.hostent = hostent
