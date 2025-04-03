.. _intro_connections:
.. _connections:

Introduction
=================
The *eta_connect.connections* module is meant to provide a standardized interface for multiple different
protocols which are used in factory operations or for the optimization of factory operations. Two important
protocols which we encounter regularly are **Modbus TCP** and **OPC UA**. In addition to this  we have also created
connections for additional API which we work with.

The *eta_connect* connection format has the advantage that it can be used for many different kinds of protocols
and APIs, with the limitation that some of them do not support all functions (for example, specific APIs/protocols
may not provide write access). Each connection can contain multiple *Nodes* (see below). These are used as the
default data points when reading data from the connection. Read data will be returned in a
:py:class:`pandas.DataFrame` with the node names as column names.

The *connections* module also provides subscription handlers which take data read from connections in regular
intervals and for example store it in files or in memory for later access. These subscription handlers can handle
multiple different connections (with different protocols) at the same time.

The *LiveConnect* class is specifically designed to combine the functionality from the *eta_x* and *connections*
modules. It can establish connections and provides an interface equivalent to the classes in the *simulators*
module. This allows easy substitution of simulation models with actual connections to real machines (or the other
way). When trying to deploy a model into operation this substitution can be very useful.

The connections are based on the concept of *Nodes* to which we establish connections. A *Node* object is a
unique description of a specific data point and includes all information required to establish a connection and
read data from the specified data point. Each data point has its own node, not just each device (or connection)
that we are connecting to. Therefore, *Nodes* are the easiest way to instantiate connections, however they can
be a bit unwieldy to work with when trying to read many different data points from the same device.

See :ref:`Connection instantiation <connection instantiation>` for more information on how to create connections.



Nodes
----------
Each *Node* object uniquely identifies a specific data point. All *Node* objects have some information in
common. This information identifies the device which the data point belongs to and can also contain information
required for authentication with the device. Depending on the protocol the *Node* object contains additional
information to correctly identify the data points.

The URL may contain the username and password (``schema://username:password@hostname:port/path``). This is handled
automatically by the connections and the username and password will be removed before creating a connection.


.. autoclass:: eta_connect.nodes::Node
    :noindex:

The following classes are there to document the required parameters for each type of node.

.. autoclass:: eta_connect.nodes::LocalNode
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve
    :noindex:

Node Typing
---------------
Eta-connect provides a generic type :attr:`Nodes[N]` which can be used to type a sequence or set of nodes. This is useful when
working with multiple nodes and you want to ensure that all nodes are of the same type.

  .. code-block:: python

    from eta_connect.connections import Node, ModbusNode, OpcuaNode
    from eta_connect.util.type_annotations import Nodes

    # Example of typing nodes
    modbus_node: ModbusNode = Node("modbus://localhost:502/0/0", "modbus", ...)
    opcua_node: OpcuaNode = Node("opcua://localhost:4840/0/0", "opcua", ...)
    nodes: Nodes[ModbusNode] = [modbus_node]

    # This will raise a type error
    nodes: Nodes[ModbusNode] = [modbus_node, opcua_node]

    # Use *Node* to allow different types of nodes
    nodes: Nodes[Node] = [modbus_node, opcua_node]
    # or explicitly list the types
    nodes: Nodes[ModbusNode | OpcuaNode] = [modbus_node, opcua_node]


.. _connection instantiation:


Connection Instantiation
=========================
| There are multiple ways to instantiate connections, depending on the use case.
  The two most common methods are :attr:`Connection.from_node()` and :attr:`Connection.from_nodes()`.
| Instantiation with :attr:`from_node(s)` is useful if you already have created some node(s) and would like to create connection(s)
  from them.
| Each connection class also has its own :attr:`_from_node()` method, since the necessary/accepted keywords might differ. To create connections, a password
  and a username are often required. For setting these the following prioritization applies:

- If a password is given in the node, take it.
- If there is no password there, take as "default" a password from the arguments.
- If there is neither, the username and password are empty.

Creating one or more Connections from node(s)
-----------------------------------------------
If you have one or multiple nodes, use :attr:`from_nodes`. Create all of the :class:`Node` objects first and pass them in a list.
:attr:`from_nodes` then returns a dictionary of connections and automatically assigns the nodes to their correct connection.
It requires less duplicate information than direct instantiation.

.. autofunction:: eta_connect.connections.base_classes::Connection.from_nodes
    :noindex:

Create one Connection
----------------------
If you have one or more :class:`Node` objects for the same hostname/protocol and just want to create one connection, you should use the :attr:`from_node` method of
the :class:`Connection` class.

.. autofunction:: eta_connect.connections.base_classes::Connection.from_node
    :noindex:

Direct Instantiation (not recommended)
---------------------------------------
| Instantiate a connection directly if you prefer to set up the connection manually, and know the specific details required.
  This method is straightforward, but requires you to explicitly handle all the connection details.
| However, you do need to create :class:`Node` objects to tell the connection where (from which data points) to read data from or write data to.
| It's also possible to pass a list of nodes, but for this use case the :attr:`from_node` method is recommended.

.. code-block:: python

    # Example for a Modbus connection
    from eta_connect.connections import ModbusConnection

    url = "modbus://192.168.178.123:502"
    username = ("admin",)
    password = "admin"

    connection = ModbusConnection(url=url, usr=username, pwd=password)

Using from_ids
---------------------------------------
The :attr:`from_ids()` method is helpful if you do not require access to the nodes and just want to quickly create a single
connection.

 .. note::
    This is not available for all connections, since the concept of IDs does not apply universally. An
    example is shown :ref:`connections`. Refer to the API documentation of the connection you would like to use to see if the
    method exists and which parameters are required.

.. autofunction:: eta_connect.connections::EneffcoConnection.from_ids
    :noindex:
