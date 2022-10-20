.. _juggler:

Juggler communication protocol
==============================

Juggler is communication protocol used for communication between back-end and
GUI front-end parts of components. As underlying protocol, Juggler uses
WebSocket communication and text messages encoding JSON data. Communication
between peers is symmetrical full duplex - once client and server establish
WebSocket communication, each party can send messages independently of other
and no further distinction between client and server is made.


Model
-----

As prerequisite for Juggler communication, each peer should implement data
model consisting of local and remote data. Data can be arbitrary application
specific JSON serializable data.

Initially, `null` value is assumed for both local and remote data.

Each peer can freely change local data. Once local data is changed, JSON patch
between previous and current local data is generated and transmitted to
other peer. Upon receiving data change, other peer applies JSON patch to it's
remote data and notifies of remote data change. This enables continuous
synchronization of local and remote data on both peers.


Communication
-------------

Juggler provides communication based on continuous synchronization of JSON data
and communication based on asynchronous message passing.

Local and remote data synchronization assumes existence of time delayed caching
implementation. Once local data changes, peer should wait for predefined
time period prior to sending changes to other peer. In this time period,
peer expects other local data changes which should all be delivered as single
change to other peer. This caching provides optimization of message number and
size of data exchanged between peers. At same time, additional communication
latency is introduced.

When transfer of data as they are is required, asynchronous message passing
should be used. By explicitly sending JSON messages, each peer can transmit
arbitrary data. This communication assumes that no additional caching is
done by Juggler implementation. Asynchronous message passing is independent
of continuous data synchronization communication.


Messages
--------

All messages are UTF-8 encoded JSON data defined by following JSON Schema::

    type: object
    required:
        - type
        - payload
    properties:
        type:
            enum:
                - DATA
                - MESSAGE
                - PING
                - PONG

`DATA` messages are used for continuous synchronization of JSON data. It's
`payload` parameter contains JSON patch value as defined by
https://tools.ietf.org/html/rfc6902. This messages are sent by peer once
local data changes.

`MESSAGE` messages provide asynchronous message passing communication.

`PING` and `PONG` messages provide simple keep alive mechanism.


Remote procedure call
---------------------

.. note::

    Juggler RPC is optional extension to base Juggler communication.
    Support for this functionality is not mandatory.

Exchange of asynchronous `MESSAGE` messages can be used as basis for RPC
implementation. For this implementation, only messages, where payload is
object containing property ``type`` with value ``rpc``, are used. All
other messages are considered "regular" asynchronous messages - Juggler RPC
passes them to user without additional processing.

Payload of RPC messages is defined by following JSON Schema::

    oneOf:
      - type: object
        required:
            - type
            - id
            - direction
            - action
            - args
        properties:
            type:
                const: rpc
            id:
                type: integer
            direction:
                const: request
            action:
                type: string
            args:
                type: array
      - type: object
        required:
            - type
            - id
            - direction
            - success
            - result
        properties:
            type:
                const: rpc
            id:
                type: integer
            direction:
                const: response
            success:
                type: boolean

As with other asynchronous messages, Juggler RPC provides full-duplex
communication. Each peer can initiate rpc exchange at any time.

Single rpc exchange (session) consists of single request message and paired
response message. Initiator of new session sends initial request message
with `id` identifier. Each peer manages it's own identifier counter which
is incremented with new request message sent by that peer. Once other peer
receives rpc request, it should respond with response message containing
`id` same as in request message.
