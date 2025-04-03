from __future__ import annotations

from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING

from eta_connect.nodes import Node

if TYPE_CHECKING:
    from typing import Any


from eta_connect.subhandlers.subhandler import SubscriptionHandler

log = getLogger(__name__)


class MultiSubHandler(SubscriptionHandler):
    """The MultiSubHandler can be used to distribute subscribed values to multiple different subscription handlers.
    The handlers can be registered using the register method.
    """

    def __init__(self) -> None:
        super().__init__()

        self._handlers: list = []

    def register(self, sub_handler: SubscriptionHandler) -> None:
        """Register a subscription handler.

        :param SubscriptionHandler sub_handler: SubscriptionHandler object to use for handling subscriptions.
        """
        if not isinstance(sub_handler, SubscriptionHandler):
            raise TypeError("Subscription Handler should be an instance of the SubscriptionHandler class.")

        self._handlers.append(sub_handler)

    def push(self, node: Node, value: Any, timestamp: datetime | None = None) -> None:
        """Receive data from a subscription. This should contain the node that was requested, a value and a timestamp
        when data was received. Push data to all registered sub-handlers.

        :param node: Node object the data belongs to.
        :param value: Value of the data.
        :param timestamp: Timestamp of receiving the data.
        """
        for handler in self._handlers:
            handler.push(node, value, timestamp)

    def close(self) -> None:
        """Finalize and close all subscription handlers."""
        for handler in self._handlers:
            try:
                handler.close()
            except Exception:
                pass
