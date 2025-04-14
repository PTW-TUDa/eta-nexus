.. _subscription_handlers:

Subscription Handlers
======================
Subscription Handlers can be used to perform operations on data which is received by connections during a running
subscription. They are required by the subscription method of each connection. Any class which has a *push* and a
*close* function fulfills the interface.

In addition to some normal subscription handlers, *eta_nexus* offers a *MultiSubHandler*, which can combine the
actions of multiple subscription handlers.

.. autoclass:: eta_nexus.subhandlers::CsvSubHandler
    :members:
    :noindex:

.. autoclass:: eta_nexus.subhandlers::DFSubHandler
    :members:
    :noindex:

.. autoclass:: eta_nexus.subhandlers::MultiSubHandler
    :members:
    :noindex:
