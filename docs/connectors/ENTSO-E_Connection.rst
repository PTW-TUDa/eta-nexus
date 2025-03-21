.. _entso-e_connection:

ENTSO-E Connection
======================
ENTSO-EConnection
----------------------------------------------------
.. autoclass:: eta_connect.connectors.node::NodeEntsoE
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve
    :noindex:

NodeENTSO-E
----------------------------------------------------
.. autoclass:: eta_connect.connectors::ENTSOEConnection
    :members:
    :noindex:

Example Usage
----------------------------------------------------
An example using the **ENTSO-E connection**:

.. literalinclude:: ../../examples/connectors/read_series_entsoe.py
    :start-after: --begin_entsoe_doc_example--
    :end-before: --end_entsoe_doc_example--
    :dedent:
