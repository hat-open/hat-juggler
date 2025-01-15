import * as u from '@hat-open/util';
import r from '@hat-open/renderer';

import * as juggler from '@hat-open/juggler';


let app = null;


async function main() {
    r.init();
    app = new juggler.Application();
}


window.addEventListener('load', main);
window.r = r;
window.u = u;
