#-*- coding: utf-8 -*-
from twisted.enterprise import adbapi
import psycopg2

class psycopgConnectionPool( adbapi.ConnectionPool ):
    """
    Fail-tolerant psycopg2 connection pool
    """
    def __init__( self, *connargs, **connkw ):
        return adbapi.ConnectionPool.__init__( self, 'psycopg2', *connargs, **connkw )
    
    def _runInteraction( self, interaction, *args, **kw ):
        try:
            return adbapi.ConnectionPool._runInteraction( self, interaction, *args, **kw )
        except psycopg2.OperationalError, e:
            if e[ 0 ] not in ( 2006, 2013 ):
                raise
            logger.err( "ConnectionPool got error %s, retrying operation" % ( e ) )
            conn = self.connections.get( self.threadID() )
            self.disconnect( conn )
            # try the interaction again
            return adbapi.ConnectionPool._runInteraction( self, interaction, *args, **kw )