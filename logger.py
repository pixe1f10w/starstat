#-*- coding: utf-8 -*-
from twisted.python import log

class Logger():
    """
    Slightly more user-friendly abstraction of log
    """
    visibleMessages = [ 'notice', 'debug', 'warning', 'error', 'message' ]
    def __init__( self, invisible = [] ):
        for item in invisible:
            try:
                self.visibleMessages.remove( item )
            except ValueError:
                pass
            
    def warn( self, text ):
        str = '[ WARNING ] ' + text 
        if 'warning' in self.visibleMessages:
            log.msg( str )
        
    def err( self, text ):
        str = '[ ERROR ] ' + text 
        if 'error' in self.visibleMessages:
            log.msg( str )
            
    def msg( self, text ): 
        if 'message' in self.visibleMessages:
            log.msg( text )
            
    def debug( self, text ):
        str = '[ DEBUG ] ' + text 
        if 'debug' in self.visibleMessages:
            log.msg( str )
            
    def notice( self, text ):
        str = '[ NOTICE ] ' + text 
        if 'notice' in self.visibleMessages:
            log.msg( str )

logger = Logger()