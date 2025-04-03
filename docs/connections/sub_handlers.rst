.. _subscription_handlers:

Subscription Handlers
======================
Subscription Handlers can be used to perform operations on data which is received by connections during a running
subscription. They are required by the subscription method of each connection. Any class which has a *push* and a
*close* function fulfills the interface.

In addition to some normal subscription handlers, *eta_connect* offers a *MultiSubHandler*, which can combine the
actions of multiple subscription handlers.

.. autoclass:: eta_connect.subhandlers::CsvSubHandler
    :members:
    :noindex:

.. autoclass:: eta_connect.subhandlers::DFSubHandler
    :members:
    :noindex:

.. autoclass:: eta_connect.subhandlers::MultiSubHandler
    :members:
    :noindex:
