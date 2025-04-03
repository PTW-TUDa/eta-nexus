.. _live_connect:

Live Connect
====================================================
The live connection enables direct connections to multiple devices, using different protocols. It utilizes the
*connections* module to estable connections. *LiveConnect* requires a configuration file to determine
which connections should be established. It will automatically map the node names of the connection to the
names specified in the JSON configuration file. This can helps to make the *LiveConnect* interface very similar to
the *FMUSimulator* interface from the simulators module which enables the direct substitution of simulation models
with connections to actual devices and thus the deployment of trained algorithms to real applications.

When using the step function, *LiveConnect* will determine based on the configuration whether additional actions
are required to activate or deactivate a system based on specified parameters. Let's consider the example of a
combined heat and power unit (CHP):

The CHP might have its own programmable logic controller (PLC) which can be accessed via Modbus TCP. From this
PLC we want to read detailed data regarding the status of the PLC. Additionally,
there might be a PLC for building automation which controls the set point of the CHP as well as the pumps and
valves of the hydraulic system. We want to control the CHP with set points provided by an algorithm. This data must
be written to the building automation PLC. However, before the CHP can be activated, we need to ensure that the pumps
are running and the valves are opened correctly. All of this can be achieved with the *LiveConnect* configuration.
When the class is configured correctly, we only need to call the *step* function and everything will be done
automatically.

For the example we need to configure the *system* CHP. It has two separate *servers*, the PLC of the CHP itself, which
is a modbus server and the PLC of the building automation, which is an OPC UA server. Both need to be configured
accordingly. Once this is done, the different nodes can be configured. For example we can configure nodes for reading
from the CHP, nodes for writing to the building automation and other nodes which are used to check the current status
of the system.

.. autoclass:: eta_connect.connections::LiveConnect
    :members:
    :noindex:
