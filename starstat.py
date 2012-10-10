#!/usr/bin/env python
from twisted.application import internet, service
from twisted.internet import protocol, reactor, defer
from twisted.protocols import basic

import datetime, re

from logger import logger
from pool import psycopgConnectionPool

class FastAGI( basic.LineOnlyReceiver ):
    """
    Simplified one-way (receiving-only) version of FastAGI protocol
    """
    delimiter = '\n'

    def __init__( self ):
        self.environment = {}

    def connectionMade( self ):
        logger.msg( "Received new connection" ) 

    def connectionLost( self, reason ):
        logger.msg( "Connection terminated" )

    def onClose( self ):
        return defer.Deferred()

    def lineReceived( self, line ):
        logger.debug( 'Line In: %s' % line )

        if not line.strip(): # prepare to and give control to action selector
            self.transport.loseConnection()

            callee = 'null'
            
            # only 'on_hangup' must send MEMBERINTERFACE as arg_1 
            if self.environment.has_key( 'agi_arg_1' ):
                if self.environment[ 'agi_arg_1' ] != '':
                    callee = self.environment[ 'agi_arg_1' ]
                    # extracting callee extension with regexp
                    callee = re.sub( '[a-zA-Z]+/', '', callee )
                else: 
                    # in case of outgoing call we're just get dnid as callee
                    # also this will be set in case of not answered incoming call
                    callee = self.environment[ 'agi_dnid' ]
                    
            self.factory.actionSelect( self.environment[ 'agi_network_script' ],
                                       self.environment[ 'agi_uniqueid' ],
                                       self.environment[ 'agi_callerid' ],
                                       callee )
                
        else: # fetching environmental variables
            try:
                key, value = line.split( ':', 1 )
                value = value[1:].rstrip( '\n' ).rstrip( '\r' )
            except ValueError, err:
                logger.err( "Invalid variable line: %s", line )
            else:
                self.environment[ key.lower() ] = value

class starstatService( service.Service ):
    def __init__( self, dbConnection ):
        self.ids = {}
        self.callStatuses = {}
        self.db = dbConnection
        
        # get statuses
        query = "select id, status from statuses;"
        self.db.runQuery( query ).addCallback( self.populateStatuses ).addErrback( self._queryFail )
    
    def getFactory( self ):
        f = protocol.ServerFactory()
        f.protocol = FastAGI
        f.actionSelect = self.actionSelect
        return f
    
    def _querySuccess( self, result ):
        # TODO: need something more useful here
        logger.msg( "Query committed." )
        
    def _queryFail( self, results ):
        # TODO: need something more useful here
        logger.err( "Query failed. Something bad happened to database?" )
    
    def populateStatuses( self, results ):
        for id, status in results:
            self.callStatuses[ status ] = id
    
    def addDictionaryEntry( self, list, id ):
        # TODO: maybe refactor with deffered?
        idx = int( list.pop()[ 0 ] )
        self.ids[ id ] = idx
        return idx
    
    def insertCallHistory( self, call_id, status, time ):
        query = "insert into call_history( id_status, time, id_call ) values( %i, '%s', %i );" % ( status, time, call_id )
        self.db.runOperation( query ).addCallback( self._querySuccess ).addErrback( self._queryFail )
        
    def updateCallEntry( self, start_time, now, id, callee ):
        duration = now - start_time.pop()[ 0 ]
        query = "update calls set duration = '%s', id_callee = %s where id = %i" % ( duration, callee, id )
        self.db.runOperation( query ).addCallback( self._querySuccess ).addErrback( self._queryFail )        
        
    def onQueueJoin( self, id, caller, callee ):
        now = datetime.datetime.now() 
        logger.msg( "Invoked onQueueJoin handler" )
        
        query = "begin; \
                insert into calls ( dt_start, id_caller ) values( '%s', %s ); \
                select currval('calls_id_seq');" % ( now, caller ) 
        self.db.runQuery( query ).addCallback( self.addDictionaryEntry, id ).addCallback( self.insertCallHistory, self.callStatuses[ 'QUEUE_JOIN' ], now ).addErrback( self._queryFail )
        
    def onAnswer( self, id, caller, callee ):
        now = datetime.datetime.now()
         
        logger.msg( "Invoked onAnswer handler" )
        
        if not self.ids.has_key( id ):
            logger.warn( "Something strange happened: answered a non-received call." )
        else:
            self.insertCallHistory( self.ids[ id ], self.callStatuses[ 'ANSWER' ], now )
                
    def onHangup( self, id, caller, callee ):
        now = datetime.datetime.now() 
        
        logger.msg( "Invoked onHangup handler" )
        
        if not self.ids.has_key( id ):
            logger.warn( "Something strange happened: hanged-up a non-received call." )
        else:
            # TODO: maybe it's better to do it with chain of deffereds?
            query = "select dt_start from calls where id = %i;" % ( self.ids[ id ] )
            self.db.runQuery( query ).addCallback( self.updateCallEntry, now, self.ids[ id ], callee ).addErrback( self._queryFail )
            self.insertCallHistory( self.ids[ id ], self.callStatuses[ 'HANG_UP' ], now )
            del self.ids[ id ]
	logger.msg( self.ids )
    
    def onOutgoingCall( self, id, caller, callee ):
        now = datetime.datetime.now() 
        logger.msg( "Invoked onOutgoingCall handler" )
        
        query = "begin; \
                insert into calls ( dt_start, id_caller ) values( '%s', %s ); \
                select currval('calls_id_seq');" % ( now, caller ) 
        self.db.runQuery( query ).addCallback( self.addDictionaryEntry, id ).addCallback( self.insertCallHistory, self.callStatuses[ 'OUTGOING' ], now ).addErrback( self._queryFail )
                       
    def onUnrecognised( self, id, caller, callee ):
        logger.err( "Unrecognised AGI script name. Check your Asterisk dialplan configuration." )
        
    def actionSelect( self, action, id, caller, callee ):
        takeAction = { 'on_queue_join' : self.onQueueJoin,
                      'on_answer' : self.onAnswer,
                      'on_hangup' : self.onHangup,
                      'on_outgoing_call' : self.onOutgoingCall }
        takeAction.get( action, self.onUnrecognised )( id, caller, callee )

# Next part is for organising work of starstat as twisted tac.
# It's not used when starstat is launched as twistd plugin.

#config = { 'port' : 4573,
#          'dbname' : 'sandbox',
#          'dbuser' : 'postgres',
#          'dbhost' : 'localhost',
#          'dbpass' : '' }

#application = service.Application( 'starstat' )

#hiddenMessages = [ 'debug' ]
#logger = Logger( hiddenMessages )

#dbConnection = psycopgConnectionPool( "dbname='%s' user='%s' host='%s' password='%s'"
#                                      % ( config[ 'dbname' ], config[ 'dbuser' ],
#                                          config[ 'dbhost' ], config[ 'dbpass' ] ) 
#                                      )
#s = starstatService( dbConnection )
#serv = service.IService( application )
#internet.TCPServer( config[ 'port' ], s.getFactory() ).setServiceParent( serv )
