import * as u from '@hat-open/util';
import r from '@hat-open/renderer';

import * as juggler from '@hat-open/juggler';


async function main() {
    r.init();
    window.app = new juggler.Application();
    window.app.addEventListener('connected', () => {
        console.log('connected');
    });
    window.app.addEventListener('disconnected', () => {
        console.log('disconnected');
    });
    window.app.addEventListener('notify', () => {
        console.log('notify');
    });
}


window.addEventListener('load', main);
window.r = r;
window.u = u;
