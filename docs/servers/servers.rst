.. _servers:

Servers
===========
The *servers* module in *eta_nexus* can be used to easily create servers. For example, the OPC UA Server
class enables the creation of an OPC UA server with simple variable access. The server interface is similar
to the connection interface, which makes it easy to access a server instead of a connection, for example
to publish values directly.

.. autoclass:: eta_nexus.servers::OpcuaServer
    :members:
    :noindex:

.. autoclass:: eta_nexus.servers::ModbusServer
    :members:
    :noindex:
