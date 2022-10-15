import r, { Renderer } from '@hat-open/renderer';
import * as u from '@hat-open/util';


type MsgRequest = {
    type: 'request',
    id: number,
    name: string,
    data: u.JData
};

type MsgResponse = {
    type: 'response',
    id: number,
    success: boolean,
    data: u.JData
};

type MsgState = {
    type: 'state',
    diff: u.JPatch
};

type MsgNotify = {
    type: 'notify',
    name: string,
    data: u.JData
};

type Msg = MsgRequest | MsgResponse | MsgState | MsgNotify;

export type Notification = {
    name: string,
    data: u.JData
};


function isMsgResponse(msg: Msg): msg is MsgResponse {
    return msg.type == 'response';
}

function isMsgState(msg: Msg): msg is MsgState {
    return msg.type == 'state';
}

function isMsgNotify(msg: Msg): msg is MsgNotify {
    return msg.type == 'notify';
}

export class OpenEvent extends CustomEvent<undefined> {
    declare readonly type: 'open';

    constructor() {
        super('open');
    }

}

export class CloseEvent extends CustomEvent<undefined> {
    declare readonly type: 'close';

    constructor() {
        super('close');
    }

}

export class NotifyEvent extends CustomEvent<Notification> {
    declare readonly type: 'notify';

    constructor(notification: Notification) {
        super('notify', {detail: notification});
    }

}

export class ChangeEvent extends CustomEvent<u.JData> {
    declare readonly type: 'change';

    constructor(state: u.JData) {
        super('change', {detail: state});
    }

}

export class ConnectedEvent extends CustomEvent<undefined> {
    declare readonly type: 'connected';

    constructor() {
        super('connected');
    }

}

export class DisconnectedEvent extends CustomEvent<undefined> {
    declare readonly type: 'disconnected';

    constructor() {
        super('disconnected');
    }

}

/**
 * Get default juggler server address
 */
export function getDefaultAddress(): string {
    const protocol = window.location.protocol == 'https:' ? 'wss' : 'ws';
    const hostname = window.location.hostname || 'localhost';
    const port = window.location.port;
    return `${protocol}://${hostname}` + (port ? `:${port}` : '') + '/ws';
}

/**
 * Juggler client connection
 *
 * Available events:
 *  - `OpenEvent` - connection is opened
 *  - `CloseEvent` - connection is closed
 *  - `NotifyEvent` - received new notification
 *  - `ChangeEvent` - remote state changed
 */
export class Connection extends EventTarget {
    _state: u.JData = null;
    _nextId = 1;
    _futures = new Map<number, u.Future<u.JData>>();
    _ws: WebSocket;

    /**
     * Create connection
     *
     * Juggler server address is formatted as
     * ``ws[s]://<host>[:<port>][/<path>]``. If not provided, hostname
     * and port obtained from ``widow.location`` are used instead, with
     * ``ws`` as a path.
     */
    constructor(address: string = getDefaultAddress()) {
        super();
        this._ws = new WebSocket(address);
        this._ws.addEventListener('open', () => this._onOpen());
        this._ws.addEventListener('close', () => this._onClose());
        this._ws.addEventListener('message', evt => this._onMessage(evt.data));
    }

    /**
     * Remote server state
     */
    get state(): u.JData {
        return this._state;
    }

    /**
     * WebSocket ready state
     */
    get readyState(): number {
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
     */
    async send(name: string, data: u.JData): Promise<u.JData> {
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
        const f = u.createFuture<u.JData>();
        try {
            this._futures.set(id, f);
            return await f;
        } finally {
            this._futures.delete(id);
        }
    }

    _onOpen() {
        this.dispatchEvent(new OpenEvent());
    }

    _onClose() {
        this.dispatchEvent(new CloseEvent());
    }

    _onMessage(data: string) {
        try {
            const msg = JSON.parse(data) as Msg;
            if (isMsgState(msg)) {
                this._state = u.patch(msg.diff, this._state);
                this.dispatchEvent(new ChangeEvent(this._state));
            } else if (isMsgNotify(msg)) {
                this.dispatchEvent(new NotifyEvent({
                    name: msg.name,
                    data: msg.data
                }));
            } else if (isMsgResponse(msg)) {
                const f = this._futures.get(msg.id);
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
 *  - ConnectedEvent - connected to server
 *  - DisconnectedEvent - disconnected from server
 *  - NotifyEvent - received new notification
 */
export class Application extends EventTarget {
    _statePath: u.JPath | null;
    _renderer: Renderer;
    _addresses: string[];
    _retryDelay: number | null;
    _conn: Connection | null;

    /**
     * Create application
     *
     * If `statePath` is `null`, remote server state is not synced to renderer
     * state.
     *
     * Format of provided addresses is same as in `Connection` constructor.
     *
     * If `retryDelay` is `null`, once connection to server is closed,
     * new connection is not established.
     */
    constructor(
        statePath: u.JPath | null = null,
        renderer: Renderer = r,
        addresses: string[] = [getDefaultAddress()],
        retryDelay: number | null = 5000
    ) {
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
     */
    async send(name: string, data: u.JData): Promise<u.JData> {
        if (!this._conn)
            throw new Error("connection closed");
        return await this._conn.send(name, data);
    }

    _onOpen() {
        this.dispatchEvent(new ConnectedEvent());
    }

    _onClose() {
        if (this._statePath)
            this._renderer.set(this._statePath, null);
        this.dispatchEvent(new DisconnectedEvent());
    }

    _onNotify(notification: Notification) {
        this.dispatchEvent(new NotifyEvent(notification));
    }

    _onChange(data: u.JData) {
        if (this._statePath == null)
            return;
        this._renderer.set(this._statePath, data);
    }

    async _connectLoop() {
        while (true) {
            for (const address of this._addresses) {
                this._conn = new Connection(address);
                this._conn.addEventListener('open', () => this._onOpen());
                this._conn.addEventListener('close', () => this._onClose());
                this._conn.addEventListener('notify', evt =>
                    this._onNotify((evt as NotifyEvent).detail)
                );
                this._conn.addEventListener('change', evt =>
                    this._onChange((evt as ChangeEvent).detail)
                );

                const closeFuture = u.createFuture<void>();
                this._conn.addEventListener('close', () =>
                    closeFuture.setResult()
                );

                await closeFuture;
                this._conn = null;
            }
            if (this._retryDelay == null)
                break;
            await u.sleep(this._retryDelay);
        }
    }

}