.. _juggler:

Juggler communication protocol
==============================

Juggler is communication protocol used for communication between back-end and
GUI front-end parts of components. As underlying protocol, Juggler uses
WebSocket communication and text messages encoding JSON data.

Communication between peers is asymmetrical - distinct client and server
entities are identified. Entity responsible for initiating Web socket
connection is considered client. Entity which receives request for
Web socket initialization is considered server.

After Web socket initialization, Juggler enables communication which
can be classified as:

    * request/response
    * server state synchronization
    * server notification

Each of these communication models is independent of one another and
can be conducted in parallel using single Juggler connection.


Request/response
----------------

Request/response communication is based on message exchange where client
sends `request` message after which server sends associated `response` message.

`request` messages include:

    * `id`

        Request message identifier unique to corresponding Juggler connection,
        generated by client.

    * `name`

        Label describing request semantics.

    * `data`

        Arbitrary request payload with structure corresponding to associated
        `name`.

`response` messages include:

    * `id`

        Response identifier matching associated request identifier.

    * `success`

        Boolean flag indicating successful execution of action initiated
        by client's request.

    * `data`

        Arbitrary response payload. In case `success` flag is ``true``,
        this data represents result of action execution. In case `success`
        flag is ``false``, this data represents error description associated
        with action execution.

At any time, client can send new `request` message. Upon receiving `request`
message, server must respond with `response` message containing same `id` as
provided by associated `request` message.

Parallel execution of multiple request/response sessions should be supported
(client can send new requests without receiving responses for all previously
sent requests).

Requests with empty name should not be notified to user. When server receives
request with empty name, it should immediately send response to client
with `success`` flag set to ``true`` and `data` containing same content as
received in request's data.


Server state synchronization
----------------------------

After Web socket initialization, server and client should assume existence
of single data, refereed as `server state`, with initial value of ``null``.

At any time, server can change it's local value of `server state`.
These changes should be accompanied with `state` messages sent to client.
`state` message contains description of change that is made to server's
local `server state` formatted as
`JSON Patch <https://tools.ietf.org/html/rfc6902>`_.

Consecutive changes to servers local `server state` can be buffered (with
appropriate timeout) and sent to client as single `state` message. Eventually,
client should be able to reconstruct exact value of `server state` by
consecutive application of received changes to it's own local `server state`
data.


Server notification
-------------------

At any time, server can send unsolicited `notify` messages to client.

`notify` messages include:

    * `name`

        Label describing notification semantics.

    * `data`

        Arbitrary notification payload with structure corresponding to
        associated `name`.


Messages
--------

All messages are UTF-8 encoded JSON data defined by following JSON Schema:

.. literalinclude:: ../schemas_json/messages.yaml
    :language: yaml
