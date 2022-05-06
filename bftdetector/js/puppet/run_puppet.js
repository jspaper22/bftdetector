'use strict';

const PuppetBrowser = require('./puppet_browser.js');
const fs = require('fs');
let path = require('path');

// read arguments
if(process.argv.length < 4){
    console.log('Need parameters. ex) node run_puppet.js [chrome path] [working_dir] [testing mode] [inst_id]');
    process.exit(1);
}

let chrome_path = process.argv[2];
let working_dir = process.argv[3];
let mode = process.argv[4];

let test_js = working_dir + '/tmpdir/testjs.js';
let inst_id = null;
if(process.argv.length > 5) {
    inst_id = process.argv[5];
    test_js = working_dir + '/tmpdir/inst' + inst_id + '/testjs.js';
}

let test_module = require(test_js);

let pb = new PuppetBrowser();
pb.test_mode = mode;
pb.mod_chrome_path = chrome_path;
pb.working_dir = working_dir;
pb.inst_id = inst_id;

let dumpio = true, devtool = true;
switch(mode){
    case 'disabled':
        dumpio=true;
        devtool=false;
        break;
    case 'cfmod':
        dumpio=false;
        devtool=false;
        break;
    default:
        dumpio=true;
        devtool=true;

}

test_module.test(pb, dumpio, devtool);



//
// if(mode === '0') {
//     test_module.test(pb, false, true, scriptName, test_output);
// } else if (mode === '1') {
//     test_module.test(pb, true, false, scriptName, test_output);
// } else {
//     test_module.test(pb, false, false, scriptName, test_output);
// }





