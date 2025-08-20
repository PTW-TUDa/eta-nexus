.. _wetterdienst_connection:

Wetterdienst Connection
====================================================
WetterdienstPrediction
----------------------------------------------------
.. autoclass:: eta_nexus.connections::WetterdienstPredictionConnection
    :members:
    :noindex:

WetterdienstPredictionNode
----------------------------------------------------
.. autoclass:: eta_nexus.nodes::WetterdienstPredictionNode
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve
    :noindex:

WetterdienstObservation
----------------------------------------------------
.. autoclass:: eta_nexus.connections::WetterdienstObservationConnection
    :members:
    :noindex:

WetterdienstObservationNode
----------------------------------------------------
.. autoclass:: eta_nexus.nodes::WetterdienstObservationNode
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve
    :noindex:

Example
----------------------------------------------------
An example using the **Wetterdienst connection**:

.. literalinclude:: ../../examples/connections/read_series_wetterdienst.py
    :start-after: --begin_wetterdienst_doc_example--
    :end-before: --end_wetterdienst_doc_example--
    :dedent:
