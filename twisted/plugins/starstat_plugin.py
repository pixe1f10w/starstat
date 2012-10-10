#-*- coding: utf-8 -*-
from zope.interface import implements

from twisted.application import service
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.application import internet

from starstat import starstatService
from logger import Logger
from pool import psycopgConnectionPool

class Options( usage.Options ):
    optParameters = [ [ "port", "p", 4573, "The port number to listen on." ],
                      [ "dbname", "d", "starstat", "The name of database." ],
                      [ "dbuser", "U", "postgres", "Database username." ],
                      [ "dbhost", "h", "localhost", "Database server hostname." ],
                      [ "dbpass", "P", "", "Database password." ] ]

class starstatServiceMaker( object ):
    implements( IServiceMaker, IPlugin )
    tapname = "starstat"
    description = "Asterisk call logging system"
    options = Options
    
    def makeService( self, options ):
        # redefine global logger with deactivated debug output
        hiddenMessages = []#[ 'debug' ]
        logger = Logger( hiddenMessages )

        dbConnection = psycopgConnectionPool( "dbname='%s' user='%s' host='%s' password='%s'"
                                                % ( options[ 'dbname' ], options[ 'dbuser' ],
                                                    options[ 'dbhost' ], options[ 'dbpass' ] ) 
                                                )

        s = starstatService( dbConnection )
        return internet.TCPServer( int( options[ 'port' ] ), s.getFactory() )

serviceMaker = starstatServiceMaker()
