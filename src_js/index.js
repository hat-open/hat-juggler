/** @module @hat-open/juggler
 */

import jiff from 'jiff';

import r from '@hat-open/renderer';
import * as u from '@hat-open/util';
import * as future from '@hat-open/future';


/**
 * Get default juggler server address
 *
 * @function
 * @return {string}
 */
export function getDefaultAddress() {
    const protocol = window.location.protocol == 'https:' ? 'wss' : 'ws';
    const hostname = window.location.hostname || 'localhost';
    const port = window.location.port;
    return `${protocol}://${hostname}` + (port ? `:${port}` : '') + '/ws';
}


/**
 * Juggler client connection
 *
 * Available events:
 *  - open - connection is opened (`detail` is undefined)
 *  - close - connection is closed (`detail` is undefined)
 *  - notify - received new notification (`detail` is received notification)
 *  - change - remote state changed (`detail` is new remote state)
 */
export class Connection extends EventTarget {

    /**
     * Create connection
     * @param {string} address Juggler server address, formatted as
     *     ``ws[s]://<host>[:<port>][/<path>]``. If not provided, hostname
     *     and port obtained from ``widow.location`` are used instead, with
     *     ``ws`` as a path.
     */
    constructor(address=getDefaultAddress()) {
        super();
        this._state = null;
        this._nextId = 1;
        this._futures = new Map();
        this._ws = new WebSocket(address);
        this._ws.addEventListener('open', () => this._onOpen());
        this._ws.addEventListener('close', () => this._onClose());
        this._ws.addEventListener('message', evt => this._onMessage(evt.data));
    }

    /**
     * Remote server state
     * @type {*}
     */
    get state() {
        return this._state;
    }

    /**
     * WebSocket ready state
     * @type {number}
     */
    get readyState() {
        return this._ws.readyState;
    }

    /**
     * Close connection
     */
    close() {
        this._ws.close(1000);
    }

    /**
     * Send request and wait for response
     * @param {string} name
     * @param {*} data
     * @return {*} response data
     */
    async send(name, data) {
        if (this.readyState != WebSocket.OPEN) {
            throw new Error("connection not open");
        }
        const id = this._nextId++;
        this._ws.send(JSON.stringify({
            type: 'request',
            id: id,
            name: name,
            data: data
        }));
        const f = future.create();
        try {
            this._futures.set(id, f);
            return await f;
        } finally {
            this._futures.delete(f);
        }
    }

    _onOpen() {
        this.dispatchEvent(new CustomEvent('open'));
    }

    _onClose() {
        this.dispatchEvent(new CustomEvent('close'));
    }

    _onMessage(data) {
        try {
            const msg = JSON.parse(data);
            if (msg.type == 'state') {
                this._state = jiff.patch(msg.diff, this._state);
                this.dispatchEvent(new CustomEvent('change', {
                    detail: this._state
                }));
            } else if (msg.type == 'notify') {
                this.dispatchEvent(new CustomEvent('notify', {
                    detail: {
                        name: msg.name,
                        data: msg.data
                    }
                }));
            } else if (msg.type == 'response') {
                const f = this._rpcFutures.get(msg.id);
                if (f && !f.done()) {
                    if (msg.success) {
                        f.setResult(msg.data);
                    } else {
                        f.setError(msg.data);
                    }
                }
            } else {
                throw new Error('unsupported message type');
            }
        } catch (e) {
            this._ws.close();
            throw e;
        }
    }

}


/**
 * Juggler based application
 *
 * Available events:
 *  - connected - connected to server (`detail` is undefined)
 *  - disconnected - disconnected from server (`detail` is undefined)
 *  - notify - received new notification (`detail` is received notification)
 */
export class Application extends EventTarget {

    /**
     * Create application
     * @param {?module:@hat-open/util.Path} statePath remote server state path
     * @param {module:@hat-open/renderer.Renderer} renderer renderer
     * @param {string[]} addresses juggler server addresses, see
     *     {@link module:@hat-open/juggler.Connection}
     * @param {?number} retryDelay connection retry delay in ms, does not
     *     retry if null
     */
    constructor(
        statePath=null,
        renderer=r,
        addresses=[getDefaultAddress()],
        retryDelay=5000) {

        super();
        this._statePath = statePath;
        this._renderer = renderer;
        this._addresses = addresses;
        this._retryDelay = retryDelay;
        this._conn = null;

        u.delay(() => this._connectLoop());
    }

    /**
     * Send request and wait for response
     * @param {string} name
     * @param {*} data
     * @return {*} response data
     */
    async send(name, data) {
        if (!this._conn)
            throw new Error("connection closed");
        return await this._conn.send(name, data);
    }

    _onOpen() {
        this.dispatchEvent(new CustomEvent('connected'));
    }

    _onClose() {
        if (this._statePath)
            this._renderer.set(this._statePath, null);
        this.dispatchEvent(new CustomEvent('disconnected'));
    }

    _onNotify(msg) {
        this.dispatchEvent(new CustomEvent('notify', {detail: msg}));
    }

    _onChange(data) {
        if (this._statePath == null)
            return;
        this._renderer.set(this._statePath, data);
    }

    async _connectLoop() {
        while (true) {
            for (const address of this._addresses) {
                this._conn = new Connection(address, this._syncDelay);
                this._conn.addEventListener('open', () => this._onOpen());
                this._conn.addEventListener('close', () => this._onClose());
                this._conn.addEventListener('notify', evt => this._onNotify(evt.detail));
                this._conn.addEventListener('change', evt => this._onChange(evt.detail));

                const closeFuture = future.create();
                this._conn.addEventListener('close', () => closeFuture.setResult());
                await closeFuture;
                this._conn = null;
            }
            if (this._retryDelay == null)
                break;
            await u.sleep(this._retryDelay);
        }
    }

}
