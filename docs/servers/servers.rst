.. _servers:

Servers
===========
The *servers* module in *eta_connect* can be used to easily create servers. For example, the OPC UA Server
class enables the creation of an OPC UA server with simple variable access. The server interface is similar
to the connection interface, which makes it easy to access a server instead of a connection, for example
to publish values directly.

.. autoclass:: eta_connect.servers::OpcUaServer
    :members:
    :noindex:

.. autoclass:: eta_connect.servers::ModbusServer
    :members:
    :noindex:
